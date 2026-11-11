#!/usr/bin/env python3
"""Недвижимость: оплаты квартирантов / долги / сверка и рентабельность по объектам.

Источники (не выдумывать цифры):
  по авг 2026 — Расчет_Аренда (Начисление_аренды, ИТОГИ);
  с сен 2026 — Upgraded_Rent_Database_Chronology (календарь, реестр, баланс, расходы, P&L).

Обновление: перечитать таблицы в re_finance_raw.json (+ при необходимости re_old_accruals.json)
и запустить этот скрипт. build_data.py подхватывает re_finance.json.
Всегда ровно 3 закрытых месяца от as_of, плюс текущий месяц если в источнике есть цифры.
"""
from __future__ import annotations
import json, os
from collections import defaultdict
from copy import deepcopy
from datetime import date, datetime
from calendar import monthrange

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "re_finance_raw.json")
OLD = os.path.join(HERE, "re_old_accruals.json")
OUT = os.path.join(HERE, "re_finance.json")

PROP_ORDER = ["Оливино", "Рей Пастор", "Лос Пуэблос", "Кооперасион", "Сагунто", "Украина"]
MONTH_RU = {1:"январь",2:"февраль",3:"март",4:"апрель",5:"май",6:"июнь",
            7:"июль",8:"август",9:"сентябрь",10:"октябрь",11:"ноябрь",12:"декабрь"}
TOL = 0.05

def r2(x):
    if x is None: return None
    return round(float(x) + 0.0, 2)

def add(*xs):
    s = 0.0
    any_ = False
    for x in xs:
        if x is None: continue
        s += float(x); any_ = True
    return r2(s) if any_ else None

def ym_add(ym, k):
    y, m = int(ym[:4]), int(ym[5:7])
    m += k
    while m > 12: m -= 12; y += 1
    while m < 1: m += 12; y -= 1
    return f"{y:04d}-{m:02d}"

def closed_months(as_of: date, n=3):
    y, m = as_of.year, as_of.month
    # last closed = previous month
    out = []
    cy, cm = y, m - 1
    if cm == 0: cy, cm = y - 1, 12
    for _ in range(n):
        out.append(f"{cy:04d}-{cm:02d}")
        cm -= 1
        if cm == 0: cy, cm = cy - 1, 12
    return list(reversed(out))

def iso_d(s):
    if not s: return None
    s = str(s).strip()
    if not s or s in ("0",): return None
    s = s[:10]
    try:
        datetime.strptime(s, "%Y-%m-%d")
        return s
    except ValueError:
        return None

def dd(s):
    s = iso_d(s)
    return None if not s else f"{s[8:10]}.{s[5:7]}"

def recon(expected, paid, vacant=False, nodata=False):
    if nodata:
        return "unknown"
    e = 0.0 if expected is None else float(expected)
    p = 0.0 if paid is None else float(paid)
    if vacant and abs(e) <= TOL and abs(p) <= TOL:
        return "ok"
    if expected is None and paid is None:
        return "unknown"
    if abs(p - e) <= TOL:
        return "ok"
    return "mismatch"

def st_label(st):
    return {"ok":"✅ сходится","mismatch":"⚠️ расхождение","unknown":"❓ нет данных"}[st]

def load():
    raw = json.load(open(RAW, encoding="utf-8"))
    old = json.load(open(OLD, encoding="utf-8")) if os.path.exists(OLD) else []
    return raw, old

def unit_key(pid, unit):
    return f"{pid}|{unit}"

def build():
    raw, old = load()
    as_of = date.fromisoformat(raw.get("as_of") or "2026-11-11")
    closed = closed_months(as_of, 3)
    current = as_of.strftime("%Y-%m")
    months = closed + [current]
    current_has = any(c["month"] == current for c in raw["calendar"]) or any(p["month"] == current for p in raw["payments"])
    shown = months if current_has else closed

    # --- tenancies: all directory rows, plus synthetic vacant where needed ---
    dir_rows = raw["directory"]
    # map id -> property, unit (stable)
    id_meta = {}
    for d in dir_rows:
        id_meta[d["id"]] = dict(property=d["property"], unit=d["unit"])
    id_meta.setdefault("O6-S1", dict(property="Сагунто", unit="Комната 1"))
    id_meta.setdefault("O2-O3", dict(property="Оливино", unit="Комната 3"))
    id_meta.setdefault("O4-L4", dict(property="Лос Пуэблос", unit="Комната 4"))
    id_meta.setdefault("O3-R2", dict(property="Рей Пастор", unit="Комната 2"))

    # calendar by (month, id)
    cal = {}
    for c in raw["calendar"]:
        cal[(c["month"], c["id"])] = c

    # payments by (month, id) rent / util / deposit
    pays = defaultdict(list)
    unmatched = []
    for p in raw["payments"]:
        if not p.get("id"):
            unmatched.append(p)
            continue
        pays[(p["month"], p["id"])].append(p)

    def pay_sum(month, pid, typ):
        items = [p for p in pays.get((month, pid), []) if p["type"] == typ]
        if typ == "Аренда":
            # возврат залога иногда записан типом «Аренда» — в аренду месяца не кладём
            items = [p for p in items if p["type"] == "Аренда" and not (
                ("возврат" in (p.get("note") or "").lower() or "возрат" in (p.get("note") or "").lower())
                and "залог" in (p.get("note") or "").lower()
            )]
        amt = r2(sum(p["amount"] or 0 for p in items)) if items else 0.0
        # dates: unique sorted
        dates = sorted({iso_d(p["date"]) for p in items if iso_d(p["date"])})
        conf = all(p.get("confirmed") for p in items) if items else True
        notes = [p.get("note") for p in items if p.get("note")]
        return amt, dates, conf, notes, items

    balances = {b["id"]: b for b in raw["balances"]}

    # August expected/paid from old accruals (rent only), keyed by tenant normalized + property
    def norm_tenant(s):
        if not s: return ""
        s = " ".join(s.replace(",", " ").split())
        s = s.replace("  ", " ")
        # strip parenthetical noise later via aliases
        return s

    TENANT_ALIAS = {
        "вишневое": "Вишневое",
        "Вишневое": "Вишневое",
        "Нивки 1 (206)": "Нивки 1 (206)",
        "Нивки 1": "Нивки 1 (206)",
        "Нивки 2 (409)": "Нивки 2 (409)",
        "Нивки 2": "Нивки 2 (409)",
        "Лузановка (9000грн) 24.05": "Лузановка",
        "Лузановка (9000грн)": "Лузановка",
        "Лузановка": "Лузановка",
        "Алехандро (колумбиец)": "Алехандро (колумбиец)",
        "Богдан": "Богдан",
        "Vlasov Oleksii (кооп-2)": "Власов Алексей",
        "Власов Алексей": "Власов Алексей",
        "Алексей Рей пастор": "Алексей - работы",
        "Алексей - работы": "Алексей - работы",
        "Полякова Наталья": "Полякова Наталья",
        "Чебыкина Светлана": "Чебыкина Светлана",
        "Эльвира Политаева": "Политаева Эльвира",
        "Политаева Эльвира": "Политаева Эльвира",
        "Аби Гари 16.07": "Аби Гари",
        "Аби Гари": "Аби Гари",
        "Черняну Ирина 16.07": "Черняну Ирина",
        "Черняну Ирина": "Черняну Ирина",
        "Хадим Yasmeen 09.07": "Хадим",
        "Хадим": "Хадим",
        "Литвиненко Наталья": "Литвиненко Наталья",
        "Мила, комната за 420€": "Мила",
        "Мила": "Мила",
        "Харкова Наталья 460 евро": "Харкова Наталья",
        "Харкова Наталья": "Харкова Наталья",
        "Гордеевы": "Горденко Иветта",
        "Горденко Иветта": "Горденко Иветта",
        "Пакистанец": "Пакистанец",
        "Байгуш Алексей/Фостик Владимир": "Байгуш Алексей/Фостик Владимир",
        "Шестукхина Елена": "Шестукхина Елена",
        "Бондаренко Ирина": "Бондаренко Ирина",
        "Ремонт": "Ремонт",
        "Свободная комната": None,
        "Сводобная комната": None,
    }

    def canon_tenant(s):
        s = norm_tenant(s)
        if s in TENANT_ALIAS:
            return TENANT_ALIAS[s]
        # fuzzy
        low = s.lower()
        for k, v in TENANT_ALIAS.items():
            if k.lower() == low:
                return v
        if "лузанов" in low: return "Лузановка"
        if "вишнев" in low: return "Вишневое"
        if "нивки 1" in low: return "Нивки 1 (206)"
        if "нивки 2" in low: return "Нивки 2 (409)"
        if "алехандр" in low: return "Алехандро (колумбиец)"
        if "поляков" in low: return "Полякова Наталья"
        if "чебыкин" in low: return "Чебыкина Светлана"
        if "политаев" in low or "ельвир" in low or "эльвир" in low: return "Политаева Эльвира"
        if "литвиненк" in low: return "Литвиненко Наталья"
        if "харков" in low: return "Харкова Наталья"
        if "горде" in low: return "Горденко Иветта"
        if "власов" in low or "vlasov" in low: return "Власов Алексей"
        if "хадим" in low: return "Хадим"
        if "черняну" in low: return "Черняну Ирина"
        if "аби" in low: return "Аби Гари"
        if "байгуш" in low or "фостик" in low: return "Байгуш Алексей/Фостик Владимир"
        if "шестук" in low: return "Шестукхина Елена"
        if "бондаренк" in low: return "Бондаренко Ирина"
        if "алексей" in low and "работ" in low: return "Алексей - работы"
        if "мила" in low: return "Мила"
        if "богдан" in low: return "Богдан"
        return s or None

    aug_old = {}  # (property, tenant) -> row
    for row in old:
        if row.get("period") != "2026-08":
            continue
        t = canon_tenant(row.get("tenant"))
        if not t:
            continue
        aug_old[(row["property"], t)] = row

    # Build a list of "slots": one per unit, with month-level tenant (may change)
    # Collect all unit ids we care about (ES+UA, no Colombia property)
    unit_ids = []
    seen = set()
    for d in dir_rows:
        if d["id"] not in seen:
            unit_ids.append(d["id"]); seen.add(d["id"])
    for pid in ("O6-S1","O4-L4","O2-O3","O3-R2"):
        if pid not in seen:
            unit_ids.append(pid); seen.add(pid)

    # For each unit+month, who is the tenant?
    def tenant_for(pid, month):
        c = cal.get((month, pid))
        if c:
            t = canon_tenant(c.get("tenant"))
            vacant = t is None or (c.get("tenant") or "").lower().startswith("свобод") or (c.get("tenant") or "").lower().startswith("сводоб") or (c.get("tenant") or "") == "Ремонт"
            if vacant:
                reason = "ремонт" if (c.get("tenant") or "") == "Ремонт" else "вакантно"
                return None, reason
            return t, None
        # August: from directory if overlapping, or old accruals
        if month == "2026-08":
            # find tenancy with date_in <= Aug 31 and (no out or out >= Aug 1)
            cands = [d for d in dir_rows if d["id"] == pid]
            # directory starts 01.09 for most — so August tenant is the one with date_in 01.09
            # (they were already living there) unless they moved in later
            early = [d for d in cands if d.get("date_in") and d["date_in"] <= "2026-09-01"
                     and (not d.get("date_out") or d["date_out"] >= "2026-08-01")]
            # prefer the earliest date_in among those starting on/before Sep 1
            if early:
                early.sort(key=lambda x: x.get("date_in") or "")
                t = canon_tenant(early[0]["tenant"])
                if t: return t, None
            return None, "нет строки в календаре"
        return None, "нет строки в календаре"

    # contract dates for a tenant on a unit
    def contract(pid, tenant):
        rows = [d for d in dir_rows if d["id"] == pid and canon_tenant(d.get("tenant")) == tenant]
        if not rows:
            return None, None, None, None
        # if multiple (price change), merge
        rows.sort(key=lambda x: x.get("date_in") or "9999")
        din = rows[0].get("date_in")
        dout = rows[-1].get("date_out")
        # if later row has no out, open
        if not rows[-1].get("date_out"):
            dout = None
        rate = rows[-1].get("rate")
        note = " · ".join(r["note"] for r in rows if r.get("note"))
        return din, dout, rate, note or None

    # Sagunto vacant from Nov (explicit)
    sagunto_note = (raw.get("sagunto_vacant") or {}).get("note")

    payment_rows = []
    # also keep fact units
    fact_units = {"2026-09": defaultdict(list), "2026-10": defaultdict(list)}

    for pid in unit_ids:
        meta = id_meta[pid]
        prop, unit = meta["property"], meta["unit"]
        # collect tenants appearing in shown months + August old
        tenants_in_span = []
        month_ten = {}
        for m in shown:
            t, vac = tenant_for(pid, m)
            month_ten[m] = (t, vac)
            if t and t not in tenants_in_span:
                tenants_in_span.append(t)
        # If unit has vacancies and/or tenant changes, we still show ONE row per unit
        # with per-month tenant name. That's clearer for a payments table.
        bal = balances.get(pid)
        # current tenant (for the row title): last non-vacant in shown months, else vacant
        current_t = None
        vacant_now = False
        vacant_reason = None
        for m in reversed(shown):
            t, vac = month_ten[m]
            if t:
                current_t = t
                break
            if vac:
                vacant_now = True
                vacant_reason = vac
        if pid == "O6-S1" and current >= "2026-11":
            vacant_now = True
            vacant_reason = "вакантно"
            current_t = None
        if pid == "O4-L4":
            vacant_now = True
            vacant_reason = "ремонт"
            current_t = None

        mon = {}
        for m in shown:
            t, vac = month_ten[m]
            vacant = bool(vac) or t is None
            if m == "2026-08":
                # from old accrual
                rec = aug_old.get((prop, t)) if t else None
                # try without exact tenant
                if rec is None and t:
                    for (pp, tt), row in aug_old.items():
                        if pp == prop and tt == t:
                            rec = row; break
                if rec is None and not vacant:
                    # maybe tenant name mismatch — try any old row for this property+similar
                    expected, paid, pdate, debt_m, nodata = None, None, None, None, True
                elif vacant and rec is None:
                    expected, paid, pdate, debt_m, nodata = 0, 0, None, None, False
                else:
                    expected = r2(rec.get("accrued"))
                    paid = r2(rec.get("paid"))
                    pdate = iso_d(rec.get("date"))
                    debt_m = r2(rec.get("debt")) if rec.get("debt") is not None else r2((expected or 0) - (paid or 0))
                    nodata = False
                dates = [pdate] if pdate else []
                conf, notes, util_paid, dep_paid = True, [], 0, 0
                # note Kharkova -460 etc in notes
                if rec and rec.get("date") and not iso_d(rec.get("date")):
                    notes.append(str(rec["date"]))
            else:
                c = cal.get((m, pid))
                expected = r2(c.get("rent") or 0) if c else (0 if vacant else None)
                nodata = c is None and not vacant
                paid, dates, conf, notes, _items = pay_sum(m, pid, "Аренда")
                util_paid, _, _, _, _ = pay_sum(m, pid, "Коммунальные оплаты")
                dep_paid, _, _, _, _ = pay_sum(m, pid, "Залог")
                if not c and vacant:
                    expected, paid, nodata = 0, paid or 0, False
            diff = None if (expected is None or paid is None) else r2(paid - expected)
            st = recon(expected, paid, vacant=vacant, nodata=nodata)
            # deposits are not rent — if official paid included deposit we mention in fact, not here
            cell = dict(
                expected=expected, paid=paid, paid_dates=dates, diff=diff,
                status=st, vacant=vacant, tenant=t, unconfirmed=not conf,
                util_paid=r2(util_paid) if m != "2026-08" else None,
                deposit_paid=r2(dep_paid) if m != "2026-08" and dep_paid else None,
                notes=[n for n in (notes or []) if n],
            )
            if m == "2026-08" and t == "Харкова Наталья":
                cell["notes"] = list(cell["notes"] or []) + ["в Начисление_аренды оплата −460 (как в источнике)"]
            if m == "2026-08" and t == "Алехандро (колумбиец)":
                cell["notes"] = list(cell["notes"] or []) + ["в Начисление_аренды оплачено 600; в «Подтверждение оплат» за август четыре платежа по 200 € = 800"]
            mon[m] = cell

            if m in fact_units and prop != "Украина":
                fact_units[m][prop].append(dict(
                    unit=unit, tenant=t or ("вакантно" if vacant else "—"),
                    accrued=expected, paid=paid, paid_dates=dates,
                    deposit=cell.get("deposit_paid"),
                    debt=None,  # filled later
                    date_in=None, date_out=None,
                    vacant=vacant, unconfirmed=not conf,
                ))

        debt = None
        debt_rent = debt_util = None
        if bal:
            debt = r2(bal.get("debt_total"))
            debt_rent = r2(bal.get("debt_rent"))
            debt_util = r2(bal.get("debt_util"))

        din = dout = rate = note = None
        if current_t:
            din, dout, rate, note = contract(pid, current_t)
        # if vacant sagunto
        if pid == "O6-S1" and vacant_now:
            # keep Alejandro contract as previous
            din, dout, rate, note = contract(pid, "Алехандро (колумбиец)")
            note = (note + " · " if note else "") + (sagunto_note or "вакантно")

        # fill fact debt/contract
        for m in fact_units:
            for u in fact_units[m].get(prop, []):
                if u["unit"] == unit:
                    u["debt"] = debt
                    if u["tenant"] not in ("вакантно", "—", "ремонт"):
                        a,b,rt,nt = contract(pid, u["tenant"] if u["tenant"] != current_t else current_t)
                        # use this tenant's contract
                        a,b,rt,nt = contract(pid, canon_tenant(u["tenant"]))
                        u["date_in"], u["date_out"] = a, b

        # общий статус строки — по закрытым месяцам (текущий ещё не закрыт)
        statuses = [mon[m]["status"] for m in closed]
        if any(s == "mismatch" for s in statuses):
            row_st = "mismatch"
        elif all(s == "unknown" for s in statuses):
            row_st = "unknown"
        else:
            row_st = "ok"

        payment_rows.append(dict(
            id=pid, property=prop, unit=unit,
            tenant=current_t, vacant=vacant_now, vacant_reason=vacant_reason,
            rate=r2(rate) if rate is not None else None,
            date_in=din, date_out=dout,
            debt=debt, debt_rent=debt_rent, debt_util=debt_util,
            status=row_st,
            months=mon,
            note=note,
        ))

    # sort
    uord = {"Комната 1":1,"Комната 2":2,"Комната 3":3,"Комната 4":4}
    payment_rows.sort(key=lambda r: (PROP_ORDER.index(r["property"]) if r["property"] in PROP_ORDER else 99,
                                     uord.get(r["unit"], 9), r["unit"]))

    # --- profitability ---
    # monthly income (accrued total) and expenses by property
    inc_m = defaultdict(lambda: defaultdict(lambda: dict(rent=0, util=0, total=0)))
    for c in raw["calendar"]:
        p = c["property"]
        inc_m[c["month"]][p]["rent"] = r2((inc_m[c["month"]][p]["rent"] or 0) + (c.get("rent") or 0))
        util = (c.get("light") or 0) + (c.get("water") or 0) + (c.get("inet") or 0)
        inc_m[c["month"]][p]["util"] = r2((inc_m[c["month"]][p]["util"] or 0) + util)
        inc_m[c["month"]][p]["total"] = r2((inc_m[c["month"]][p]["total"] or 0) + (c.get("total") or 0))

    # Aug income from old accruals (rent only)
    for row in old:
        if row.get("period") == "2026-08":
            p = row["property"]
            inc_m["2026-08"][p]["rent"] = r2((inc_m["2026-08"][p]["rent"] or 0) + (row.get("accrued") or 0))
            inc_m["2026-08"][p]["total"] = inc_m["2026-08"][p]["rent"]
            inc_m["2026-08"][p]["util"] = None  # not in this source as P&L-style

    CAT_KEEP = ["Электричество","Водоснабжение","Интернет","Ремонты/Обслуживание","Страховка","Налоги","Прочие расходы",
                "Коммунидад","IBI","Ипотека","Агентство"]
    exp_m = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
    for e in raw["expenses"]:
        exp_m[e["month"]][e["property"]][e["category"]] += e["amount"]

    def month_block(m, prop):
        inc = inc_m.get(m, {}).get(prop) or {}
        income = r2(inc.get("total")) if inc else None
        cats = {}
        missing_cats = []
        if m == "2026-08":
            expenses = None
            net = None
            margin = None
            missing_cats = ["все статьи расходов (коммунидад, IBI, коммуналка, ремонт, агентство, ипотека, страховка) — в старой таблице «ИТОГИ» по объектам нет"]
        else:
            byc = exp_m.get(m, {}).get(prop) or {}
            for cat in CAT_KEEP:
                if cat in byc:
                    cats[cat] = r2(byc[cat])
                elif cat in ("Коммунидад","IBI","Ипотека","Агентство","Налоги"):
                    missing_cats.append(cat)
            expenses = r2(sum(byc.values())) if byc else (0.0 if income is not None else None)
            if income is None and expenses is None:
                net = None; margin = None
            else:
                net = r2((income or 0) - (expenses or 0))
                margin = r2(((net / income) * 100) if income else None)
        return dict(
            income=income, income_rent=r2(inc.get("rent")) if inc else None,
            income_util=r2(inc.get("util")) if inc and inc.get("util") is not None else None,
            expenses=expenses, expenses_by=cats or None,
            net=net, margin_pct=margin,
            missing=missing_cats,
        )

    # annual 2026 YTD through last closed, and 2025
    def sum_old_income(year, props, through=None):
        # rent accrued from old sheet
        out = defaultdict(float)
        for row in old:
            per = row.get("period") or ""
            if not per.startswith(str(year)):
                continue
            if through and per > through:
                continue
            out[row["property"]] += row.get("accrued") or 0
        return {p: r2(out[p]) for p in props if p in out}

    ytd_through = closed[-1]  # last closed
    # 2026 YTD: Jan-Aug old (rent) + Sep-Oct new (total accrued). Don't use old Sep.
    inc_2026 = sum_old_income(2026, PROP_ORDER, through="2026-08")
    util_2026 = defaultdict(float)
    opex_2026 = defaultdict(lambda: defaultdict(float))
    for m in ("2026-09","2026-10") if ytd_through >= "2026-10" else [x for x in ("2026-09","2026-10") if x <= ytd_through]:
        for p, inc in inc_m.get(m, {}).items():
            inc_2026[p] = r2((inc_2026.get(p) or 0) + (inc.get("total") or 0))
            if inc.get("util"):
                util_2026[p] += inc["util"]
        for p, cats in exp_m.get(m, {}).items():
            for c, v in cats.items():
                opex_2026[p][c] += v

    inc_2025 = sum_old_income(2025, PROP_ORDER, through="2025-12")

    properties = []
    missing_global = []
    for prop in PROP_ORDER:
        monthly = {m: month_block(m, prop) for m in shown if m <= ytd_through or m == current}
        # annual 2026
        inc = inc_2026.get(prop)
        exp_cats = {c: r2(v) for c, v in opex_2026.get(prop, {}).items()}
        exp_tot = r2(sum(exp_cats.values())) if exp_cats else None
        # expenses incomplete (no Jan-Aug opex)
        miss_a = [
            "расходы янв–авг 2026 по объекту (в старой таблице нет разбивки)",
            "стоимость / цена покупки объекта — в таблицах аренды нет, доходность (yield) посчитать нельзя",
            "налог 24% не разнесён по объектам (есть только сводом по Испании в «ИТОГИ» / «Из чего сложилось»)",
            "коммунидад, IBI, ипотека, агентство — отдельных статей в источниках нет",
        ]
        if prop == "Украина":
            miss_a.append("эксплуатационные расходы по Украине (в «Эксплуатационные расходы» только испанские объекты)")
            if "2026-07" in (raw.get("itogi") or {}).get("ua_net", {}) or True:
                # UA net jul-aug 2026 missing in ИТОГИ
                if "2026-07" not in raw["itogi"]["ua_net"]:
                    miss_a.append("Украина нетто за июль и август 2026 в «ИТОГИ» не заполнены")
        net_a = r2((inc or 0) - (exp_tot or 0)) if inc is not None else None
        # don't present net as complete
        annual_2026 = dict(
            income=inc, expenses=exp_tot, expenses_by=exp_cats or None,
            net=net_a, margin_pct=r2((net_a / inc * 100) if inc and net_a is not None else None),
            yield_pct=None, value=None,
            partial=True,
            through=ytd_through,
            missing=miss_a,
        )
        miss_25 = [
            "расходы 2025 по объекту — в источниках нет",
            "стоимость / цена покупки — нет, yield % нет",
            "доход 2025 = начисленная аренда из «Начисление_аренды» (без компенсации коммуналки)",
        ]
        inc25 = inc_2025.get(prop)
        annual_2025 = dict(
            income=inc25, expenses=None, expenses_by=None,
            net=None, margin_pct=None, yield_pct=None, value=None,
            partial=True, missing=miss_25,
        )
        # vacant flag
        vacant = False
        vacant_note = None
        if prop == "Сагунто":
            vacant = True
            vacant_note = sagunto_note
        properties.append(dict(
            property=prop,
            vacant=vacant, vacant_note=vacant_note,
            monthly=monthly,
            annual={"2026": annual_2026, "2025": annual_2025},
        ))

    # portfolio P&L check note
    pnl_note = "Суммы начислений и расходов по объектам за сен–ноя сходятся с «Отчет P&L» с точностью до округления (±1 €)."

    # unmatched payment
    extra_notes = []
    if unmatched:
        for p in unmatched:
            extra_notes.append(
                f"В реестре {dd(p['date']) or p['date']}: «{p.get('note') or p['type']}» {r2(p['amount'])} € без ID помещения — в таблицу не разнёс."
            )

    payments_block = dict(
        title="Оплаты квартирантов · долги · сверка",
        cur="EUR",
        as_of=as_of.isoformat(),
        closed_months=closed,
        current_month=current if current_has else None,
        months=shown,
        month_labels={m: MONTH_RU[int(m[5:])] + (" (неполный)" if m == current else "") for m in shown},
        src=raw["sources"]["old"] + " · " + raw["sources"]["new"],
        fetched_at=raw["fetched_at"],
        rows=payment_rows,
        notes=[
            "Начислено и оплачено — аренда (без коммуналки и залога). Коммуналка, если была, указана в примечании месяца.",
            "Долг накопительный — из «Контроль баланса» на дату выгрузки (по помещению, включая предыдущих жильцов, если ID тот же).",
            "Всегда три закрытых месяца; ноябрь — месяц-к-дате, если в новой таблице уже есть начисления или оплаты.",
            "Сагунто (Azorín 7, 4-14): с ноября вакантно — жилец съехал, выселение закрыто, Алла сдаёт заново.",
            "В текущем (незакрытом) месяце «⚠️» значит, что к дате выгрузки начисление ещё не закрыто оплатой — это не долг за закрытый месяц.",
        ] + extra_notes,
    )

    profit_block = dict(
        title="Рентабельность по объектам",
        cur="EUR",
        as_of=as_of.isoformat(),
        closed_months=closed,
        current_month=current if current_has else None,
        months=shown,
        month_labels=payments_block["month_labels"],
        src=raw["sources"]["new"] + " · доход янв–авг 2026 и 2025 — Начисление_аренды (Расчет_Аренда)",
        fetched_at=raw["fetched_at"],
        properties=properties,
        notes=[
            pnl_note,
            "Доход с сентября — начисления арендаторам (аренда + свет/вода/интернет) из календаря. За янв–авг 2026 и за 2025 — только начисленная аренда (компенсация коммуналки в той выгрузке отдельно не сведена по объектам).",
            "Чистая за месяц = начисления − эксплуатационные расходы. Налог 24% в P&L по объектам не разнесён (статья «Налоги» = 0).",
            "Доходность (yield %) от стоимости объекта — основа: поля стоимости нет ни в одной из двух таблиц.",
            "Колумбийского портфеля в аренде нет — только Испания и Украина.",
        ],
    )

    # fact units for Из чего сложилось (official property totals stay in build_data)
    def clean_fact(dct):
        out = {}
        for prop, units in dct.items():
            out[prop] = units
        return out

    fact_units_out = {m: clean_fact(fact_units[m]) for m in fact_units}

    out = dict(
        fetched_at=raw["fetched_at"],
        as_of=as_of.isoformat(),
        payments=payments_block,
        profit=profit_block,
        fact_units=fact_units_out,
        official_paid=raw.get("official_paid"),
    )
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("wrote", OUT)
    # quick print
    print("closed", closed, "current", current, "shown", shown)
    print("payment rows", len(payment_rows))
    for r in payment_rows:
        badge = {"ok":"OK","mismatch":"DIFF","unknown":"?"}[r["status"]]
        print(f"  {r['property']:16} {r['unit']:10} {(r['tenant'] or r['vacant_reason'] or '—'):28} debt={r['debt']} {badge}")
        for m in shown:
            c = r["months"][m]
            print(f"     {m}: exp={c['expected']} paid={c['paid']} {c['status']} {c.get('tenant') or ''}")

if __name__ == "__main__":
    build()
