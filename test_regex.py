import re

DOMAIN_REGEX = re.compile(r"^(?=.{1,253}$)(?:[a-zA-Z0-9-]{1,63}\.)+[A-Za-z]{2,63}$")

test_domains = [
    "zitcom_0uowe_sign_on_mvyhhasf6j_l5umsiiu10.dranataliaxavier.com.br",
    "zitcom_ltzl8_sign_on_aygld8w1qy_a3glpap7z0.dranataliaxavier.com.br",
    "kucoin_se-login-po.godaddysites.com",
    "uphold_logp_us.godaddysites.com",
    "call_domainname_here.acafdxiaharbor.com",
    "aktualizujte-svůj-účet.weebly.com"
]

print("Testing Domains against DOMAIN_REGEX:")
for d in test_domains:
    match = DOMAIN_REGEX.fullmatch(d)
    print(f"[{'V' if match else 'X'}] {d}")
