# Kommunintegration

Första paketet beskriver det privata API:et för åldersverifiering. Det innehåller
ett [OpenAPI-kontrakt](../openapi/age-verification.json) och en
[Pythonklient](../tools/age_client.py). Kontraktet är OpenAPI 3.0.1.
Tjänsten är en pilot; endpoint, testnycklar och betrodda utfärdare avtalas separat.
Exempelvärdena i kontraktet är syntetiska och kan inte godkännas som bevis.

SAML används enligt [inloggningsguiden](saml.md). Ett åldersresultat identifierar
ingen person. Allmänna plånboksintyg och ombud har ännu inga publika Tjipp-API:er.

## Flöde i e-tjänstens server

1. Starta en session med tjänstens fasta `siteId`, origin och egen API-nyckel.
2. Förvara `id` och `binding` i den webbläsarsession som startade kontrollen.
   Lämna endast `presentation` till browsern. Skydda browserns återanrop med CSRF.
3. För DC API: skicka browserns opaka bevis till `/age/complete`.
   För OpenID4VP: läs `/age/poll` tills ett slutläge nås.
4. Tillåt åtgärden först efter ett lyckat `/age/consume`. HTTP 200 eller
   `state: VERIFIED` är inte ett konsumerat godkännande.
5. Avbrott anropar `/age/cancel`. Utgång, fel eller okänt utfall ger inget tillstånd.

Klientexempel från repots rot, i e-tjänstens serverkod:

```python
import os
from tools.age_client import AgeClient

client = AgeClient(os.environ['TJIPP_API_ORIGIN'], 'municipality',
                   os.environ['TJIPP_SITE_KEY'], 'https://service.example')
session = client.start('dc_api')
# Spara session i den aktuella server-sessionen. Returnera bara presentation.
presentation = session.presentation
```

Efter browserns separata, CSRF-skyddade återanrop:

```python
state = client.complete(session, browser_credential)
if state == 'VERIFIED' and client.consume(session):
    allow_age_restricted_action()
```

`session` måste hämtas från samma autentiserade server-session; ta aldrig emot
`binding` eller API-nyckeln från browsern. Tillståndet gäller den åtgärd som
e-tjänsten bundit till sessionen. `AgeClientError` ger inget godkännande.

## Plattformar

| Plattform | Första anslutning | Separat autentisering |
|---|---|---|
| WSO2 API Manager | Importera OpenAPI-filen. Sätt den avtalade HTTPS-backenden och mappa rutterna till exakt `/age/*`. | Kommunens klient autentiseras hos WSO2. Gatewayn använder rätt sajts hemliga API-nyckel mot Tjipp. |
| Frends | Använd `Frends.HTTP.Request` i en serverprocess. Skicka POST, JSON och rätt sajts hemliga nyckel. Importera kontraktet om processen även ska exponeras som API. | Den anropande tjänsten ska vara autentiserad och bunden till en registrerad sajt. Nyckeln hämtas från skyddad konfiguration. |
| Azure API Management / Logic Apps | Importera kontraktet i API Management eller använd HTTP-actions. [Start-action](../examples/azure/start-action.json) visar meddelandet. | Entra-/gatewayautentisering är en separat del. `Authorization` till Tjipp innehåller sajtnyckeln, inte kommunens Entra-token. |

Detta är anslutningsunderlag, inte färdiga driftsättningar. Ingen av de tre
leverantörsmiljöerna har provats i detta paket. WSO2 Identity Server och Entra
External ID behöver egna SAML/OIDC-prov; en API-import verifierar inte inloggning.

## Gateway och processinställningar

- Bind den autentiserade klienten till rätt `siteId` och origin. Låt aldrig en
  anropare välja en annan sajts backendnyckel genom att ändra JSON-kroppen.
- Backendens Host ska motsvara den fasta HTTPS-adressen. Skicka bara de headers
  som behövs: `Authorization`, `Content-Type` och HTTP-klientens framing.
  Backend avvisar `Origin`, `Forwarded` och `X-Forwarded-*`. Stäng av automatisk
  vidarebefordran av dessa headers; ta inte bort verifierarens kontroller.
- TLS-verifiering ska vara på. Nycklar, binding, råa intyg och request/response-
  kroppar ska inte hamna i körhistorik, tracing eller felsökningsloggar.
- Inaktivera caching och automatiska återförsök för `start`, `complete` och
  `consume`. Ett förlorat svar från `consume` är ett okänt utfall; kör inte om
  åtgärden. Starta en ny användarkontroll vid behov.
- Skicka JSON med känd Content-Length, utan chunked Transfer-Encoding.
  Hela kroppen får vara högst 128 KiB. Proxy-timeout måste rymma verifieringen.
- Pollning ska vara begränsad av `expiresIn`. Ingen nedgradering till ett
  enklare verifieringssätt efter nekande eller tekniskt fel.

## Acceptans per faktisk plattform

Kör med registrerade syntetiska testidentiteter och testnycklar. Spara plattform,
version, konfigurationens revision, Tjipp-revision, datum och utfall för:

| Prov | Förväntat utfall |
|---|---|
| Giltigt signerad presentation och konsumtion | Exakt `{"age_over_18": true}` en gång |
| Samma konsumtion igen | Nekad |
| Annan sajts nyckel, origin eller session | Nekad |
| Browser skickar `age_over_18: true` utan bevis | Inget godkännande |
| Manipulerat bevis, okänd utfärdare eller utgång | Inget godkännande |
| Avbruten kontroll | Inget godkännande |
| Timeout efter skickad konsumtion | Okänt utfall; ingen automatisk retry |
| Logg- och historikgranskning | Inga nycklar, binding eller råa bevis |

Det lokala helkedjeprovet använder verklig TLS och kryptografi, men egen
syntetisk utfärdare och programvaruplånbok. Det ersätter inte proven ovan.

## Källor

- [WSO2 OpenAPI-import](https://apim.docs.wso2.com/en/latest/api-design-manage/design/create-api/create-rest-api/create-a-rest-api-from-an-openapi-definition/)
- [Frends HTTP Request](https://tasks.frends.com/tasks/Frends.HTTP.Request)
- [Frends OpenAPI](https://docs.frends.com/guides/api-management/how-to-create-an-api-with-frends)
- [Azure OpenAPI-import](https://learn.microsoft.com/en-us/azure/api-management/import-api-from-oas)
- [Logic Apps: skyddade in- och utdata](https://learn.microsoft.com/en-us/azure/logic-apps/logic-apps-securing-a-logic-app)
- [Logic Apps: återförsök](https://learn.microsoft.com/en-us/azure/logic-apps/error-exception-handling)
