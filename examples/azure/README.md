# Logic Apps: start-action

`start-action.json` är ett action-fragment för en befintlig, skyddad
serverprocess. Det är inte ett komplett workflow eller en ARM-mall.

Definiera `TjippApiOrigin`, `TjippSiteId` och `TjippSiteOrigin` som fasta
konfigurationsparametrar och `TjippSiteKey` som `SecureString`, med värdet från
hemlighetslagring. Ingen av dem får hämtas från browserns anrop.

Bind workflow-körningen till e-tjänstens server-session. Bara `presentation`
får lämnas till browsern. Alla efterföljande actions som hanterar svar eller
bevis behöver egna skyddade in- och utdata. Fragmentet ger inte detta skydd
automatiskt åt hela workflowet.

Verifiera headers, Content-Length, TLS, timeout och körhistorik i den aktuella
Logic Apps-miljön enligt [acceptansproven](../../docs/kommunintegration.md).
Fragmentet har kontrollerats som JSON men ännu inte körts i Azure.
