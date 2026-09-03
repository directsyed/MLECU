"""QLoRA fine-tune of Qwen3.6-27B on pilot-mix-v3, arm C training run (2026-07-22 night).

WHAT THIS DOES (morning-read version): loads the verified BF16 checkpoint with its weights
quantized on-the-fly to 4-bit NF4 (frozen scaffolding, never updated, chosen because a
27B in Q8 is 27GB and cannot fit one 24GB card with training overhead), bolts full-precision
LoRA adapters (rank 16) onto every attention and MLP projection matrix, and trains ONLY the
adapters on the 242 chat transcripts, watching the 28-pair held-out slice for the
memorization turn (best-checkpoint-by-eval-loss = early stopping). The launcher exports
CUDA_VISIBLE_DEVICES=0 so the process physically cannot see the convicted 3090.

Numbers that matter: ~15-16GB base + ~0.4GB adapters/optimizer + activations on 24GB;
242 examples x 3 epochs / (batch 1 x accum 8) = ~90 optimizer steps; lr 2e-4 cosine.

Run (chain does this):
  CUDA_VISIBLE_DEVICES=0 car/.venv/bin/python ml/finetuning/train.py [--smoke]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE / "models/Qwen3.6-27B"
DATA = HERE / "data"
OUT = HERE / "runs/qlora-v1"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true",
                    help="2 optimizer steps then exit 0, chain gate before the real run")
    args = ap.parse_args()

    import torch
    from datasets import load_dataset
    from peft import LoraConfig
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from trl import SFTConfig, SFTTrainer

    assert torch.cuda.device_count() == 1, \
        "expected exactly 1 visible GPU (the Ti), launcher must set CUDA_VISIBLE_DEVICES=0"
    print(f"training on: {torch.cuda.get_device_name(0)}")

    bnb = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",          # levels placed on the weight bell curve
        bnb_4bit_use_double_quant=True,      # quantize the block scales too (~0.4b/param saved)
        bnb_4bit_compute_dtype=torch.bfloat16,
    )
    model = AutoModelForCausalLM.from_pretrained(
        BASE, quantization_config=bnb, device_map={"": 0},
        torch_dtype=torch.bfloat16, trust_remote_code=False)
    model.config.use_cache = False           # KV cache is inference-only; conflicts with ckpt
    tokenizer = AutoTokenizer.from_pretrained(BASE)

    lora = LoraConfig(
        r=16, lora_alpha=32, lora_dropout=0.05, bias="none", task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"])

    ds = load_dataset("json", data_files={
        "train": str(DATA / "train.jsonl"), "val": str(DATA / "val.jsonl")})

    common = dict(
        output_dir=str(OUT), seed=0, bf16=True,
        # 04:20 fix (attempt 3): trl's default "chunked_nll" loss upcasts the WHOLE lm_head
        # weight to fp32 per chunk (vocab 124k x 5120 x 4B = the 2.37GiB OOM, independent of
        # seq length). "nll" keeps the head in bf16; logits at our lengths are ~250MB peak.
        loss_type="nll",
        # 04:55 fix (attempt 4): epoch-1 EVAL pass OOM'd (2.69GiB), eval batch defaults
        # to 8 and the eval loop accumulates logits on-GPU. We need only eval_loss.
        per_device_eval_batch_size=1,
        prediction_loss_only=True,
        per_device_train_batch_size=1, gradient_accumulation_steps=8,
        learning_rate=2e-4, lr_scheduler_type="cosine", warmup_ratio=0.1,
        optim="paged_adamw_8bit", logging_steps=5, report_to=[],
        gradient_checkpointing=True,
        gradient_checkpointing_kwargs={"use_reentrant": False},
        max_length=512, packing=False,   # measured: longest transcript = 484 tokens (04:30
                                         # fix, 1024 OOM'd the fp32 logits chunk in trl's
                                         # loss: 2.37GiB ask vs 1.61 free on the Ti)
    )
    if args.smoke:
        sft = dict(common, max_steps=2, eval_strategy="no", save_strategy="no")
    else:
        sft = dict(common, num_train_epochs=3,
                   eval_strategy="epoch", save_strategy="epoch", save_total_limit=3,
                   load_best_model_at_end=True, metric_for_best_model="eval_loss",
                   greater_is_better=False)

    # assistant_only_loss: mask loss to assistant turns (the reply is the lesson, not the
    # question). Supported by current trl for chat datasets; fall back with a loud log if
    # this build rejects it.
    try:
        cfg = SFTConfig(**sft, assistant_only_loss=True)
        print("assistant_only_loss: ON")
    except TypeError:
        cfg = SFTConfig(**sft)
        print("assistant_only_loss: NOT SUPPORTED by this trl, full-sequence loss (logged)")

    trainer = SFTTrainer(model=model, args=cfg, peft_config=lora,
                         train_dataset=ds["train"],
                         eval_dataset=None if args.smoke else ds["val"],
                         processing_class=tokenizer)
    result = trainer.train()

    if args.smoke:
        print(f"SMOKE OK: {result.metrics}")
        return

    trainer.save_model(str(OUT / "adapter"))         # adapter weights only (~100-200MB)
    tokenizer.save_pretrained(str(OUT / "adapter"))
    (OUT / "train_summary.json").write_text(json.dumps({
        "metrics": result.metrics,
        "log_history": trainer.state.log_history,    # full loss curves for the morning read
        "best_checkpoint": trainer.state.best_model_checkpoint,
        "best_eval_loss": trainer.state.best_metric,
    }, indent=2))
    print(f"DONE. best eval_loss={trainer.state.best_metric} "
          f"(checkpoint {trainer.state.best_model_checkpoint}); adapter -> {OUT/'adapter'}")


if __name__ == "__main__":
    main()
