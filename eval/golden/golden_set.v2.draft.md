# Golden set v2 — draft for review

40 questions: v1's 18 (ids 1–18, wording unchanged) + 22 new (ids 19–40).
After approval this becomes `golden_set.v2.json`; v1 is not edited.

| Type | v1 | New | Total |
|---|---|---|---|
| 5G (normal) | 6 | 7 | 13 |
| 4G (normal) | 0 | 8 | 8 |
| Mixed 4G/5G trap (adversarial) | 6 | 2 | 8 |
| Obvious off-topic | 5 | 0 | 5 |
| Telecom-sounding off-topic | 1 | 2 | 3 |
| 3GPP, but not in our 3 specs | 0 | 3 | 3 |

**How the new in-domain sections were chosen:** seeded random draw (seed `20261023`) from clauses with ≥400 chars of text, excluding frontmatter, annexes, Void, change history, General/Overview/Scope/Definitions/Abbreviations and v1's gold clauses; the first sections in draw order were used, none were skipped.
**Wording:** **T** = worded from the section title, **B** = worded from body text in different words (7 T / 8 B among new in-domain).
**Gold sections** match by prefix: a sub-section counts as a hit for its parent.

---

## A. v1 normal questions (wording unchanged; answer quote added)

| id | Spec | Question | Gold sections | Answer sentence (exact, from the spec) |
|---|---|---|---|---|
| 1 | 5G | What is the role of the AMF in the 5G system architecture? | 23.501/6.2.1 | "The Access and Mobility Management function (AMF) includes the following functionality. … -Termination of RAN CP interface (N2). -Termination of NAS (N1), NAS ciphering and integrity protection. -Registration management. -Connection management. -Reachability management. -Mobility Management." |
| 2 | 5G | How does the UE initiate a PDU session establishment in 5GS? | 24.501/6.4.1.2, 24.501/6.4.1.1 | "In order to initiate the UE-requested PDU session establishment procedure, the UE shall create a PDU SESSION ESTABLISHMENT REQUEST message." |
| 3 | 5G | Which network function is responsible for selecting the SMF? | 23.501/6.3.2 | "The SMF selection functionality is supported by the AMF and SCP and is used to allocate an SMF that shall manage the PDU Session." |
| 4 | 5G | What is the structure of the 5G-GUTI? | 23.501/5.9.4, 24.501/9.11.3.4 | "The 5G-GUTI shall be structured as: <5G-GUTI> := <GUAMI> <5G-TMSI>" |
| 5 | 5G | Describe the states of 5GMM (5GS Mobility Management) in the UE. | 24.501/5.1.3.2, 24.501/5.1.3.1 | "In the state 5GMM-DEREGISTERED, no 5GMM context has been established and the UE location is unknown to the network and hence it is unreachable by a network." (plus the sibling state sections 5GMM-NULL, -REGISTERED-INITIATED, -REGISTERED, -DEREGISTERED-INITIATED, -SERVICE-REQUEST-INITIATED) |
| 6 | 5G | What is the purpose of the Network Slice Selection Assistance Information (NSSAI)? | 23.501/5.15.1, 23.501/5.15.2 | "The NSSAI is a collection of S-NSSAIs. … The Requested NSSAI signalled by the UE to the network allows the network to select the Serving AMF, Network Slice(s) and Network Slice instance(s) for this UE, as specified in clause 5.15.5." |

## B. v1 trap questions (wording unchanged; gold sections added — #39)

Expected behaviour for all traps: name the generation mismatch, then answer each part from its own spec.

| id | Question | The trap | Gold sections | Answer sentence(s) |
|---|---|---|---|---|
| 7 | When an MME receives an Attach Request, does it communicate with the UDM? | MME is 4G, UDM is 5G; they meet only as the combined HSS+UDM in interworking | 24.301/5.5.1.2.2, 23.501/6.2.7, 23.501/5.17.2.1 | 24.301: "In state EMM-DEREGISTERED, the UE initiates the attach procedure by sending an ATTACH REQUEST message to the MME…" · 23.501: "When the HSS+UDM is required to provide the subscription data to the MME, for each APN, only one SMF+PGW-C FQDN and associated APN is provided to the MME…" |
| 8 | What timer does the AMF use for a Tracking Area Update in EPS? | AMF is 5G; EPS uses the MME and T3412; 5G uses periodic registration and T3512 | 24.301/5.3.5, 24.501/5.3.7 | 24.301: "The periodic tracking area updating procedure is used to periodically notify the availability of the UE to the network. The procedure is controlled in the UE by timer T3412." · 24.501: "The procedure is controlled in the UE by the periodic registration update timer, T3512." |
| 9 | During a 5G registration, how is the EPS bearer identity allocated? | EBIs are a 4G concept; 5G allocates them only for interworking, via the AMF | 23.501/6.2.1, 23.501/5.17.2.1, 24.301/6.4.1.2 | 23.501 (AMF functions): "-EPS Bearer ID allocation for interworking with EPS." · 24.301: "The MME shall assign and include an EPS bearer identity in the ACTIVATE DEFAULT EPS BEARER CONTEXT REQUEST message…" |
| 10 | Does the SGW connect to the SMF for user plane traffic? | SGW is 4G; in interworking its user plane goes to the combined UPF+PGW-U, controlled by SMF+PGW-C over N4 | 23.501/5.17.1.2, 23.501/4.3.1 | "In order to support the interworking with EPC, the SMF+PGW-C provides information over N4 to the UPF+PGW-U related to the handling of traffic over S5-U." |
| 11 | Explain how the PDN Gateway handles 5G QoS flows. | PGW is 4G and handles EPS bearers; QoS flows are 5G (UPF/SMF); only the combined SMF+PGW-C / UPF+PGW-U spans both | 23.501/5.7, 23.501/5.17.1.2, 23.501/4.3.1 | "NOTE 2: PGW-C + SMF and UPF + PGW-U are dedicated for interworking between 5GS and EPC… UEs that are not subject to 5GS and EPC interworking may be served by entities not dedicated for interworking, i.e. by either by PGW or SMF/UPF." |
| 12 | What is the message format for a 5G Session Management Tracking Area Update? | Tracking Area Update is a 4G EMM message; 5GSM has no such message | 24.301/8.2.29, 24.501/8.3 | 24.301: "Message type: TRACKING AREA UPDATE REQUEST … Direction: UE to network" (the 5GSM message list in 24.501 8.3 contains no TAU message) |

## C. v1 off-topic (unchanged)

| id | Kind | Question | Expected |
|---|---|---|---|
| 13 | obvious | What is the capital of France? | refuse |
| 14 | obvious | Can you explain how to bake a chocolate cake? | refuse |
| 15 | telecom-sounding (borderline) | What is the difference between TCP and UDP? | refuse, or say it's out of scope |
| 16 | obvious | Who won the World Cup in 2022? | refuse |
| 17 | obvious | Write a python script to parse an XML file. | refuse |
| 18 | obvious | What are the side effects of aspirin? | refuse |

---

## D. New 5G questions (7)

| id | Style | Question | Gold section | Answer sentence (exact) |
|---|---|---|---|---|
| 19 | T | When a UE is registered over both 3GPP and non-3GPP access in the same PLMN, does the AMF give it one 5G-GUTI or one per access? | 23.501/5.3.2.4 | "When the 3GPP access and the non-3GPP access for the same UE are served by the same PLMN, the AMF assigns the same 5G-GUTI for use over both accesses." |
| 20 | B | If a phone is idle on the cellular side but still connected to the 5G core over Wi-Fi, how does the network reach it when downlink data arrives for the cellular side? | 23.501/5.3.3.4 | "When the UE CM state in the AMF is CM-IDLE for 3GPP access and CM-CONNECTED for Non-3GPP access, the AMF shall perform a network triggered Service Request procedure, when it has downlink data to be sent to this UE for 3GPP access, by sending either the Paging Request via 3GPP access or the NAS notification via Non-3GPP access to this UE" |
| 21 | T | How are Configuration Transfer messages routed between RAN nodes in 5GS? | 23.501/5.26.2.2 | "The AMF uses the destination address to route the message to the correct AMF via the N14 interface." |
| 22 | B | After a 5G residential gateway receives cause #28 "Restricted service area" over wireline access, which 5GMM state does it enter? | 24.501/5.3.5.3 | "…shall start enforcing the wireline access service area restrictions and shall enter the state 5GMMREGISTERED.NON-ALLOWED-SERVICE." |
| 23 | B | When a UE performs a registration update only because its periodic timer T3512 expired, what registration type does it indicate? | 24.501/5.5.1.3.2 | "If case b) is the only reason for initiating the registration procedure for mobility and periodic registration update, the UE shall indicate "periodic registration updating" in the 5GS registration type IE" · case b): "when the periodic registration updating timer T3512 expires in 5GMM-IDLE mode;" |
| 24 | T | In the network-initiated de-registration procedure, what does the UE do if the lower layers report that the DEREGISTRATION ACCEPT message failed to transmit? | 24.501/5.5.2.3.4 | "The de-registration procedure shall be progressed and the UE shall send the DEREGISTRATION ACCEPT message." |
| 25 | B | Which timer does a UE start when it sends its first REGISTRATION REQUEST to join the 5G network? | 24.501/5.5.1.2.2 | "The UE initiates the registration procedure for initial registration by sending a REGISTRATION REQUEST message to the AMF, starting timer T3510." |

## E. New 4G questions (8)

| id | Style | Question | Gold section | Answer sentence (exact) |
|---|---|---|---|---|
| 26 | T | What does the MME do if an EMM INFORMATION message is not delivered because of a handover? | 24.301/5.4.5.4 | "If the EMM INFORMATION message could not be delivered due to an intra MME handover and the target TA is included in the TAI list, then upon successful completion of the intra MME handover the MME shall retransmit the EMM INFORMATION message." |
| 27 | B | In LTE, can the network limit how often an IoT device sends user data inside control-plane NAS messages, and how long does that limit last? | 24.301/6.3.8 | "The UE shall limit the rate at which it generates uplink NAS messages with user data over control plane to comply with the serving PLMN policy provided by the network. The indicated rate in a NAS procedure applies to the PDN connection the NAS procedure corresponds to, and the indicated rate is valid until the PDN connection is released." |
| 28 | T | What are the possible values of the EPS update status? | 24.301/5.1.3.3 | "EU1: UPDATED … EU2: NOT UPDATED … EU3: ROAMING NOT ALLOWED" |
| 29 | B | In EPS, if an ESM uplink message fails to send and the UE has moved to a tracking area outside its TAI list, what happens to the ESM procedure? | 24.301/6.3.3 | "If lower layers indicate a TAI change, but the current TAI is not in the TAI list, the ESM procedure shall be aborted and re-initiated after successfully performing a tracking area updating procedure." |
| 30 | T | What is the TRACKING AREA UPDATE REQUEST message used for in N1 mode? | 24.301/5.5.5 | "The tracking area updating procedure is used to construct a TRACKING AREA UPDATE REQUEST message for the inter-system change from S1 mode to N1 mode for further security verification by the MME." |
| 31 | B | How should an LTE UE respond when it receives an EPS NAS message that is missing a mandatory information element? | 24.301/7.5.1 | "…the UE shall return a status message (EMM STATUS or ESM STATUS depending on the PD) with cause #96 "invalid mandatory information"" |
| 32 | T | How does the MME start a network-initiated transport of NAS messages? | 24.301/5.6.4.3 | "Upon request from an application to send a message encapsulated in the generic transport of NAS message, the EMM entity in the MME initiates the procedure by sending a DOWNLINK GENERIC NAS TRANSPORT message including the corresponding message in the generic message container IE." |
| 33 | B | When an LTE UE wants to change the guaranteed bit rate of a bearer without touching its packet filters, what does it put in the request? | 24.301/6.5.4.2 | "To request a change of the GBR without changing the packet filter(s), the UE shall set the TFT operation code in the Traffic flow aggregate IE to "no TFT operation" and include the packet filter identifier(s) to which the change of the GBR applies in the Packet filter identifier parameter in the parameters list." |

## F. New trap questions (2)

| id | Question | The trap | Gold sections | Answer sentences |
|---|---|---|---|---|
| 34 | When the AMF sends a DOWNLINK GENERIC NAS TRANSPORT message to the UE, which IE carries the application's message? | DOWNLINK GENERIC NAS TRANSPORT is the 4G (MME) message; the AMF uses DL NAS TRANSPORT with a Payload container | 24.301/5.6.4.3, 24.501/5.4.5.3 | 24.301: "…the EMM entity in the MME initiates the procedure by sending a DOWNLINK GENERIC NAS TRANSPORT message including the corresponding message in the generic message container IE." · 24.501: "In 5GMM-CONNECTED mode, the AMF initiates the NAS transport procedure by sending the DL NAS TRANSPORT message" |
| 35 | Does the UE start timer T3510 when it sends an ATTACH REQUEST to the MME? | T3510 is the 5G registration timer; a 4G attach starts T3410 | 24.301/5.5.1.2.2, 24.501/5.5.1.2.2 | 24.301: "In state EMM-DEREGISTERED, the UE initiates the attach procedure by sending an ATTACH REQUEST message to the MME, starting timer T3410 and entering state EMM-REGISTERED-INITIATED" · 24.501: "…sending a REGISTRATION REQUEST message to the AMF, starting timer T3510." |

## G. New off-topic questions (5)

| id | Kind | Question | Why it's off-topic | Expected |
|---|---|---|---|---|
| 36 | telecom-sounding | How does Wi-Fi 6 use OFDMA to share a channel between devices? | IEEE 802.11ax, not 3GPP; "Wi-Fi" may look in-domain (corpus covers WLAN access) | refuse / not covered |
| 37 | telecom-sounding | What is the maximum downstream speed of a DOCSIS 3.1 cable modem? | CableLabs spec; the corpus names DOCSIS only as a reference for cable gateways — a deliberately hard negative | refuse / not covered |
| 38 | 3GPP, not in corpus | How many HARQ processes does the NR MAC support in the downlink? | TS 38.321 (NR MAC), not indexed | say the indexed specs don't cover it |
| 39 | 3GPP, not in corpus | What does the PDCP discard timer control in NR? | TS 38.323 (NR PDCP), not indexed; 0 corpus hits | say the indexed specs don't cover it |
| 40 | 3GPP, not in corpus | Which Diameter command does the MME send to the HSS over S6a to update the UE's location? | TS 29.272; the corpus only lists it as a reference | say the indexed specs don't cover it |

---

### Notes for review
- **Q11** points at `23.501/5.7` (all QoS-model sub-sections) because v1 named 5.7.1/5.7.2, which don't exist as chunks — the QoS model lives in its sub-sections. Say if you'd rather pin specific ones.
- **Q12 and Q38–40** have no chunk containing the "answer" — the correct behaviour is to notice what's missing. Q12 still has gold sections so retrieval can be scored on finding the real TAU message.
- **Q30** is a 4G-spec section about the 4G→5G handover. I kept it as 4G (it's where the draw landed), but it doubles as a realistic cross-generation question.
