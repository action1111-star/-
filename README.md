# Subdomain Radar

بيراقب Subdomains جديدة على قايمة دومينات من HackerOne scope، ويبعت تنبيه Discord لما يلاقي حاجة جديدة.

## الإعداد

1. حط قايمة الـ scope الخام بتاعتك (نفس الصيغة اللي عندك، wildcard في كل سطر) في:
   `data/scope.txt`

2. ضيف الـ Secret في Settings → Secrets and variables → Actions:
   - `DISCORD_WEBHOOK_URL`

3. الـ workflow بيشتغل أوتوماتيك كل 12 ساعة، أو شغله يدوي من تبويب Actions.

## ملاحظات

- أول تشغيلة بتاخد baseline بس من غير تنبيهات (عشان متتبعتش آلاف الرسايل أول مرة).
- بعد كده أي subdomain جديد يظهر لأي دومين هيبعتلك تنبيه فورًا.
- الداتابيز (`data/subdomains_db.json`) بيتحدث ويتعمله commit تلقائي بعد كل تشغيلة.
