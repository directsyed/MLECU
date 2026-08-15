// Isolated compile+behaviour test of the helpers added to FastECU.
// Minimal stubs for the Qt bits so the LOGIC can be verified without Qt installed.
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <string>
#include <cstdio>

struct QByteArray {
    std::string s;
    QByteArray(const char* p=""): s(p?p:"") {}
    bool isEmpty() const { return s.empty(); }
    QByteArray trimmed() const {
        size_t a=s.find_first_not_of(" \t\r\n"); if(a==std::string::npos) return QByteArray("");
        size_t b=s.find_last_not_of(" \t\r\n");
        QByteArray r; r.s=s.substr(a,b-a+1); return r;
    }
    unsigned toUInt(bool* ok, int base) const {
        errno=0; char* end=nullptr;
        unsigned long v=strtoul(s.c_str(), &end, base);
        *ok = (end && *end=='\0' && end!=s.c_str() && errno==0);
        return (unsigned)v;
    }
};
static QByteArray g_env("");
static QByteArray qgetenv(const char*) { return g_env; }

// ---- code under test (verbatim from the patch) ----
static bool env_override_active()
{
    return !qgetenv("FASTECU_SID34_FORMAT").isEmpty();
}

static uint8_t sid34_data_format_identifier()
{
    const QByteArray env = qgetenv("FASTECU_SID34_FORMAT");
    if (env.isEmpty())
        return 0x04;
    bool ok = false;
    const unsigned parsed = env.trimmed().toUInt(&ok, 0);
    if (!ok || parsed > 0xFF)
        return 0x04;
    return (uint8_t)parsed;
}
// ---- end code under test ----

static int fails=0;
static void check(const char* env, uint8_t want, bool want_override, const char* why){
    g_env=QByteArray(env);
    uint8_t got=sid34_data_format_identifier();
    bool ov=env_override_active();
    bool ok=(got==want && ov==want_override);
    if(!ok) fails++;
    printf("  %-22s -> 0x%02X override=%d  %s  (%s)\n", env[0]?env:"(unset)", got, ov,
           ok?"PASS":"*** FAIL ***", why);
}
int main(){
    printf("=== sid34_data_format_identifier behaviour ===\n");
    check("",      0x04, false, "unset must preserve upstream 0x04");
    check("0x00",  0x00, true,  "hex form");
    check("0",     0x00, true,  "decimal form");
    check("0x04",  0x04, true,  "explicit default still flags override");
    check("4",     0x04, true,  "decimal 4");
    check("0xFF",  0xFF, true,  "max valid");
    check("0x100", 0x04, true,  "out of range -> safe default");
    check("garbage",0x04,true,  "malformed -> safe default, no crash");
    check("  0x02 ",0x02,true,  "whitespace tolerated");
    printf("\n%s (%d failures)\n", fails? "*** FAILURES ***":"ALL PASS", fails);
    return fails?1:0;
}
