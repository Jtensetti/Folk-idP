# Folk-idP

Integrationsunderlag och testverktyg för tjänster som vill ansluta till Tjipp.
Materialet är [MIT-licensierat](LICENSE): kostnadsfritt att använda och anpassa,
även kommersiellt. Tjipps identitetsregister och utfärdande ingår inte.

## Börja här

1. Följ [SAML-guiden](docs/saml.md) för er test-SP.
2. Använd separata testnycklar och syntetiska identiteter.
3. Prova inloggning, avbrott, sessionsbindning och felaktiga svar.

Verktygen kräver Python 3, OpenSSL och Bash. Inga Pythonpaket behöver installeras.

```sh
python3 -m unittest discover -s tools -p 'test_*.py'
bash tools/generate-sandbox-certs.sh
python3 tools/metadata_preflight.py --help
```

Nyckelgeneratorn skapar lokala testnycklar och vägrar skriva över befintliga filer.
Metadatakontrollen granskar struktur och profil; den verifierar inte XML-signaturen
eller medlemskap i en federation. Använd ert SAML-bibliotek för tillitskontrollen.

## Produktionsanslutning

Installation och lokala tester är kostnadsfria. Åtkomst till Tjipps driftade tjänst
kräver separat avtal, godkända motparter och produktionsnycklar. Priser och
lanseringsdatum är inte fastställda. Tjipp saknar ännu Digg-godkännande.
OIDC, åldersverifiering och appens plånboksfunktioner är inte färdiga kundgränssnitt.

Kontakt: [Jonatan Tensetti](mailto:Jonatan@tensetti.se).
