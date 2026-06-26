# Чек-лист DNS для почты pricemonitor.tech

Цель: письма от `noreply@pricemonitor.tech` проходят аутентификацию (SPF + DKIM + DMARC),
и в почтовых клиентах рядом с письмом показывается логотип (BIMI / логотип в Яндекс.Почте).

Записи добавляются в панели **nic.ru** (DNS-зона домена). Делать строго по порядку:
сначала 1–3, дать им «прижиться» и убедиться, что письма проходят, и только потом 4.

Текущее состояние (проверено): SPF — нет, **DKIM — есть** (селектор `postbox`),
DMARC — нет, BIMI — нет. Осталось сделать: SPF, DMARC, BIMI.
Verification-TXT `sanitazer-pricemonitor` уже есть — **не удалять**.

Поле «Имя/Host» в nic.ru указывается относительно домена (без `pricemonitor.tech`).
Корень домена — `@`.

---

## 1. SPF  (обязательно)

- Тип: `TXT`
- Имя: `@`
- Значение: `v=spf1 include:<INCLUDE_ИЗ_POSTBOX> -all`

`<INCLUDE_ИЗ_POSTBOX>` — точное значение include берётся в консоли Yandex Cloud Postbox
на странице домена (раздел проверки/настройки домена). Должна быть только **одна** TXT-запись
SPF на домене; если SPF уже появится — не дублировать, а дополнить существующую.

- [ ] добавлено
- [ ] проверено: `dig +short TXT pricemonitor.tech` показывает строку `v=spf1 ... -all`

---

## 2. DKIM  ✅ ГОТОВО

Уже настроено ранее. Селектор — `postbox`.

- Тип: `TXT`
- Имя: `postbox._domainkey`
- Значение: `v=DKIM1;h=sha256;k=rsa;p=…` (RSA-ключ присутствует)

- [x] добавлено
- [x] проверено: `dig +short TXT postbox._domainkey.pricemonitor.tech` возвращает ключ

---

## 3. DMARC  (обязательно)

Шаг 3a — запускаем в режиме мониторинга (никого не блокирует):

- Тип: `TXT`
- Имя: `_dmarc`
- Значение: `v=DMARC1; p=none; rua=mailto:dmarc@pricemonitor.tech; adkim=s; aspf=s`

- [ ] добавлено
- [ ] 2–3 дня собираем отчёты на `dmarc@pricemonitor.tech`, убеждаемся, что письма
      проходят SPF и DKIM с выравниванием (alignment)

Шаг 3b — после того как письма стабильно проходят, поднимаем политику (обязательное
условие для BIMI):

- Имя: `_dmarc`
- Значение: `v=DMARC1; p=quarantine; pct=100; rua=mailto:dmarc@pricemonitor.tech; adkim=s; aspf=s`

(ещё строже — `p=reject`)

- [ ] политика поднята до `quarantine` (или `reject`)
- [ ] проверено: `dig +short TXT _dmarc.pricemonitor.tech`

---

## 4. BIMI  (логотип в письме — только после п.3b)

Логотип уже готов: `frontend/public/bimi-logo.svg` → после деплоя доступен по
`https://pricemonitor.tech/bimi-logo.svg` (формат SVG Tiny PS, проверен).

- Тип: `TXT`
- Имя: `default._bimi`
- Значение: `v=BIMI1; l=https://pricemonitor.tech/bimi-logo.svg;`

- [ ] SVG реально открывается по https-ссылке (после деплоя фронта)
- [ ] запись добавлена
- [ ] проверено: `dig +short TXT default._bimi.pricemonitor.tech`

Важно: **Gmail** покажет логотип только при наличии **VMC** (платный сертификат на
зарегистрированный товарный знак). Без VMC логотип показывают Яндекс и часть других
клиентов. Параметр VMC добавляется в ту же запись как `a=https://.../vmc.pem`.

---

## Альтернатива для Яндекс.Почты (без BIMI и VMC)

Зелёный кружок «PR» в Яндекс.Почте проще сменить через **Яндекс 360 / Postmaster**:
подтвердить домен, настроить DKIM/DMARC (п.2–3 выше) и загрузить логотип в кабинете.
Это работает без VMC и отдельной BIMI-записи.

- [ ] домен подтверждён в Яндекс Postmaster
- [ ] логотип загружен в кабинете

---

## Быстрая проверка всего разом

```sh
echo "SPF:";   dig +short TXT pricemonitor.tech
echo "DKIM:";  dig +short TXT postbox._domainkey.pricemonitor.tech
echo "DMARC:"; dig +short TXT _dmarc.pricemonitor.tech
echo "BIMI:";  dig +short TXT default._bimi.pricemonitor.tech
```

Онлайн-проверки: mxtoolbox.com (SPF/DKIM/DMARC), bimigroup.org/bimi-generator (BIMI/SVG).
