# Marknadssignaler — Guld, OMX30, Nasdaq

Ett litet system som varje dag/halvtimme kollar tekniska signaler (MA20/MA50,
RSI14, MACD) for Guld, OMX Stockholm 30 och Nasdaq Composite, och skickar en
push-notis till din mobil nar laget byter mellan LONG / SHORT / NEUTRAL.

Allt kor gratis pa GitHubs egna servrar (GitHub Actions) — du behover inget
eget serverutrymme.

## Hur det hanger ihop

```
GitHub Actions (schemalaggare, kor var 30:e min)
        |
        v
signal_check.py  --  hamtar priser via yfinance, raknar ut MA/RSI/MACD
        |
        v
state.json  --  minns senaste laget per tillgang (sa du inte far notis i onodan)
        |
        v
ntfy.sh  --  skickar push-notisen till ntfy-appen pa din mobil
```

## Se signalerna på en webbsida (valfritt)

Repot innehåller `index.html` — en enkel sida som läser `state.json` live och
visar pris, läge och indikatorer för alla tre tillgångar. För att få en riktig
länk till den:

1. I repot: **Settings → Pages**.
2. Under "Build and deployment" → Source: **Deploy from a branch**.
3. Branch: **main**, mapp: **/ (root)** → **Save**.
4. Vänta en minut, ladda om sidan — du får en länk i stil med
   `https://ditt-användarnamn.github.io/marknadssignaler/`
5. Den sidan uppdaterar sig varje gång du laddar om den, med det senaste som
   finns i `state.json` (dvs. senast körda schemaläggning).

## Vad jag redan har byggt at dig

- `signal_check.py` — hela logiken: hamtar data, raknar ut indikatorer, avgor
  LONG/SHORT/NEUTRAL, skickar notis vid lagesbyte. Testad med paahittad
  prisdata i sandboxen (jag har inte natverksatkomst till Yahoo Finance harifran,
  sa den skarpa korningen sker forst hos dig via GitHub Actions).
- `requirements.txt` — de fyra Python-paket som behovs.
- `.github/workflows/check-signals.yml` — schemat som kor scriptet automatiskt.
- `state.json` — tom fran borjan, fylls i automatiskt.
- `history.json` — tom lista fran borjan; fylls pa med varje lagesbyte (max 50 senaste), sa sidan kan visa "Senaste uppdateringar".

## Det du behover gora (cirka 15-20 minuter, en gang)

### 1. Installera ntfy pa din mobil
- Ladda ner appen **ntfy** (finns pa App Store och Google Play, gratis, ingen
  inloggning kravs).
- I appen: tryck "+" och lagg till ett **eget, svarbissat amnesnamn** —
  t.ex. `mert-marknad-x7k2` (nagot du hittar pa som ingen annan sannolikt
  anvander, eftersom vem som helst som vet namnet kan se dina notiser).
- Skriv ner det namnet — det ar din `NTFY_TOPIC`.

### 2. Skapa ett GitHub-konto (om du inte redan har ett)
- Gratis, pa github.com.

### 3. Skapa ett nytt repo och ladda upp filerna
- Pa github.com: "New repository" → dopa det t.ex. `marknadssignaler` →
  valj **Private** (sa ingen annan ser din setup) → skapa.
- Ladda upp alla filer jag byggt (dra-och-slapp fungerar pa GitHubs webbsida,
  eller anvand `git push` om du ar van vid det).

### 4. Lagg in ditt ntfy-amne som en hemlighet
- I ditt repo: **Settings → Secrets and variables → Actions → New repository secret**
- Namn: `NTFY_TOPIC`
- Varde: det amnesnamn du valde i steg 1 (t.ex. `mert-marknad-x7k2`)
- Spara.

### 5. Testa korningen manuellt
- Ga till fliken **Actions** i ditt repo.
- Valj workflowen "Kolla marknadssignaler" i vanstermenyn.
- Tryck **Run workflow** → **Run workflow** igen for att bekrafta.
- Efter nagon minut: kolla att korningen blev gron (bock). Om nagot av
  lagena rakar vara LONG eller SHORT redan forsta gangen far du en notis
  direkt i ntfy-appen — annars star det bara "NEUTRAL" i loggen, vilket ar
  forvantat.

### 6. Lut dig tillbaka
- Fran och med nu kor GitHub Actions scriptet automatiskt var 30:e minut
  (vardagar 07-22 UTC — justera tiderna i `.github/workflows/check-signals.yml`
  om du vill ha annan tid).
- Du far bara en notis nar ett lage faktiskt **byter** (t.ex. NEUTRAL → LONG),
  inte varje gang scriptet kor.

## Att justera senare

- **Tickers**: `signal_check.py`, i `ASSETS`-dictionaryn. Just nu:
  `GC=F` (guldterminer — Yahoo saknar en fungerande gratis-ticker for rent
  spot-guld, se avsnittet "Om guldpriset" nedan), `^OMX` (OMX Stockholm 30),
  `^NDX` (Nasdaq-100,
  motsvarar det de flesta mäklare kallar "US Tech 100 cash").
- **Signalregler**: funktionen `determine_signal()` i signal_check.py — kräver
  nu MA20/MA50 + RSI + MACD + volymbekräftelse + att dagstrenden håller med
  (se "Hur signalen räknas ut" nedan). Lägg gärna till fler villkor om du vill
  ha strängare eller mjukare trösklar.
- **Schema**: cron-raden i workflow-filen (`*/5 7-22 * * 1-5` betyder
  "var 5:e minut, 07-22 UTC, mandag-fredag").

## Hur signalen raknas ut (utokad version)

Sedan senaste uppdateringen kravs FEM villkor samtidigt for LONG (och motsatta
fem for SHORT) - stangare an bara MA/RSI/MACD:

1. **MA20 vs MA50** - kortsiktig trend (som innan)
2. **RSI** - inte overkopt/oversald (som innan)
3. **MACD-histogram** - fart at ratt hall (som innan)
4. **Volym** - senaste candelns volym maste ligga over sitt eget 20-periods-
   snitt, annars racknas rorelsen som svagt bekraftad
5. **Dagstrend** - MA20/MA50 pa DAGSKURSER (separat fran de 5-minuters-kurser
   signalen annars anvander) maste peka samma hall - ett multi-tidsram-filter
   sa en kortsiktig studs inte tolkas som en trend

Dessutom beraknas, som extra kontext (paverkar INTE sjalva LONG/SHORT/NEUTRAL):

- **ATR-baserat stop/target-forslag**: stop = 1.5xATR fran priset,
  target = 2xATR. Ett rakneexempel pa rimlig risk/reward, inte en
  rekommendation.
- **Makrokontext**: dollarindex (`DX-Y.NYB`) for guld, amerikanska
  10-arsrantan (`^TNX`) for index. Visas som bakgrundsinfo pa sidan.

### backtest.py - statistisk validering

`backtest.py` kor SAMMA GRUNDREGLER (MA/RSI/MACD/volym, utan dagstrend-filtret
eftersom det redan racknas pa dagsniva) mot 2 ars historisk DAGSDATA, och
skriver ut trafffsakerhet och snittavkastning per signal, jamfort med
kop-och-behall. Kor den sa har:

```
pip install -r requirements.txt
python backtest.py
```

Lasvart INNAN du drar slutsatser: backtestet kor pa dagskurser, inte samma
5-minuters-upplosning som den live signalen anvander, sa resultatet ar en
fingervisning - inte ett exakt bevis for hur 5-minuterssystemet skulle ha
presterat historiskt. Transaktionskostnader och spread racknas inte heller
med.

## Om guldpriset

`GC=F` ar guldterminer (COMEX futures), inte exakt samma som det "cash"/spot-pris
din maklare visar. De ligger normalt ~0.5-1.5% ifran varandra, vilket ar
normalt for termins- kontra spotpriser, inte ett fel. Yahoo Finance saknar
tyvarr en fungerande gratis-ticker for rent spot-guld (flera varianter
testades: `XAU=X`, `XAUUSD=X` — inga fungerar), och TradingViews egna
TVC:GOLD-flode ar proprietart och inte tillgangligt via gratis-API:er.

## Viktigt att ha i huvudet

- Det har ar ett **tekniskt underlag**, inte en garanti — MA/RSI/MACD slapar
  alltid efter priset och ger falska signaler ibland, sarskilt i sidledes
  marknader.
- Jag ar inte finansiell radgivare, och det har ska inte ses som
  investeringsradgivning. Testa/pappershandla signalerna ett tag innan du
  later dem styra riktiga positioner.
- yfinance hamtar data fran Yahoo Finance, vilket ar gratis men inte ett
  officiellt/garanterat API — om Yahoo andrar nagot kan scriptet behova
  smaputsningar. Hor av dig om en korning borjar felas i Actions-fliken, sa
  hjalper jag dig fixa det.
- Varje korning gor nu fler anrop till Yahoo (3 tillgangar x 5-minutersdata +
  3 dagstrend-kollar + 2 makrotickers = 8 anrop). Om korningar borjar fela
  ofta pa var-5:e-minut-schemat kan det bero pa att Yahoo tillfalligt
  strypper anrop - saktar da ner till t.ex. var 15:e minut i workflow-filen.
- Systemet saknar fortfarande: nyheter/handelser, bolagsfundamenta, statistisk
  validering pa den faktiska 5-minutersdatan, och positionsstorlek anpassad
  efter din egen risktalighet. Se backtest.py for den narmaste vi kommer en
  statistisk koll just nu.
