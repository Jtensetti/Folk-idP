# SAML

Använd ett underhållet SAML-bibliotek eller er befintliga inloggningsförmedlare.
Sätt upp en separat test-SP med HTTPS, exakt ACS-adress och egna nycklar för
signering och dekryptering.

## Sandbox

Registrering och tillitsankare hanteras i
[Sweden Connects sandbox](https://sandbox.swedenconnect.se/home/saml.html).
Tjipp har separata testflöden för syntetisk identitet och appgodkännande.
Börja med det syntetiska flödet:

| Inställning | Värde |
|---|---|
| EntityID | `https://tjipp-sweden-connect-sandbox.onrender.com/idp` |
| IdP-metadata | `https://tjipp-sweden-connect-sandbox.onrender.com/saml2/metadata` |
| Federationens IdP-metadata | `https://md.sandbox.swedenconnect.se/metadata/mdx/role/idp.xml` |
| Begäran / svar | HTTP-Redirect / HTTP-POST |
| AuthnContext | `urn:openid:lab:simulated` |
| ForceAuthn / IsPassive | `true` / `false` |

Validera federationens metadatasignatur mot dess officiella tillitsankare och
kontrollera giltighet innan uppgifterna används. Hämta adresser och certifikat
ur validerad metadata. En nedladdad XML-fil är inte i sig betrodd.

Skicka en signerad AuthnRequest, bekräfta simulerad identitet och välj
`TEST-CREDENTIAL-alice`. Svaret får inte behandlas som en verklig person eller LoA3.
Testmiljön kan vara vilande och certifikat kan löpa ut; kontrollera aktuell
metadata före test. Kontakta oss för aktuell tillgång till appflödet.

## Acceptans

| Fall | Förväntat resultat |
|---|---|
| Giltigt svar | Session för rätt syntetiskt subjekt |
| Avbrott eller nekande | Ingen ny session |
| Fel signatur, issuer, audience, destination eller recipient | Avvisat svar |
| Fel InResponseTo, RelayState eller webbläsarsession | Avvisat svar |
| Utgånget eller återspelat svar | Avvisat svar |
| LoA3 begärs från det syntetiska flödet | Nekat svar utan assertion |

Kör negativa fall mot er egen isolerade SP. Spara revision och utfall utan privata
nycklar eller sessionsvärden. Produktionsanslutning får egna metadata, nycklar och
avtal; kopiera inte sandboxens tillitsankare till produktion.
