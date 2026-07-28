#!/usr/bin/env python3
"""Проставляет name_el в data/signs.json (колода «экзаменационный минимум», 63 карточки).

В отличие от полного каталога, у рукописной колоды нет источника с греческими
подписями: её знаки нарисованы вручную и не привязаны к driving.cy. Поэтому таблица
ниже выверена вручную. Пометка в третьей колонке:

  catalog  — формулировка дословно взята из data/signs_full.json (официальная
             подпись с https://driving.cy/el/signs);
  adapted  — формулировка каталога, сокращённая или уточнённая под конкретную
             карточку (например, добавлено значение «50» к «όριο ταχύτητας»);
  new      — понятия нет в каталоге (фазы светофора, часть разметки), формулировка
             составлена в терминологии каталога.

Запуск: python3 scripts/add_greek_mini.py [--dry-run]
"""
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data", "signs.json")
DRY_RUN = "--dry-run" in sys.argv

# id карточки -> (греческое название, происхождение)
NAMES = {
    # --- предупреждающие ---
    "warn_bend_right":    ("Στροφή δεξιά", "adapted"),
    "warn_crossroads":    ("Διασταύρωση", "new"),
    "warn_roundabout":    ("Κυκλικός κόμβος (προειδοποίηση)", "catalog"),
    "warn_zebra":         ("Διάβαση πεζών", "catalog"),
    "warn_children":      ("Συχνή χρήση δρόμου από παιδιά", "catalog"),
    "warn_roadworks":     ("Οδικά έργα", "catalog"),
    "warn_slippery":      ("Ολισθηρό οδόστρωμα", "catalog"),
    "warn_descent":       ("Απότομη κατηφόρα", "catalog"),
    "warn_narrows":       ("Στένωση οδού", "adapted"),
    "warn_signals":       ("Φωτεινή σηματοδότηση μπροστά", "catalog"),
    "warn_animals":       ("Άγρια ζώα", "catalog"),
    "warn_giveway_ahead": ("Παραχώρηση προτεραιότητας μπροστά", "catalog"),
    "warn_hump":          ("Ανώμαλο ύψωμα οδοστρώματος", "catalog"),
    "warn_rocks":         ("Πτώση βράχων", "catalog"),

    # --- приоритет ---
    "prio_stop":          ("Σήμα στάσης", "catalog"),
    "prio_giveway":       ("Παραχώρηση προτεραιότητας", "catalog"),
    "prio_main":          ("Δρόμος προτεραιότητας", "catalog"),
    "prio_main_end":      ("Τέλος δρόμου προτεραιότητας", "catalog"),

    # --- запрещающие ---
    "proh_noentry":       ("Απαγόρευση εισόδου", "catalog"),
    "proh_speed50":       ("Ανώτατο όριο ταχύτητας 50", "adapted"),
    "proh_speed_end":     ("Τέλος ανώτατου ορίου ταχύτητας", "catalog"),
    "proh_overtake":      ("Απαγόρευση προσπεράσματος", "catalog"),
    "proh_nowaiting":     ("Απαγόρευση στάθμευσης", "catalog"),
    "proh_nostopping":    ("Απαγόρευση στάσης και στάθμευσης", "catalog"),
    "proh_nouturn":       ("Απαγόρευση αναστροφής", "catalog"),
    "proh_noleft":        ("Απαγόρευση αριστερής στροφής", "catalog"),
    "proh_nohorn":        ("Απαγόρευση χρήσης κόρνας", "catalog"),
    "proh_nomotor":       ("Απαγόρευση μηχανοκίνητων οχημάτων", "catalog"),
    "proh_height":        ("Απαγόρευση οχημάτων ύψους άνω των 3,8 μ.", "adapted"),
    "proh_width":         ("Απαγόρευση οχημάτων πλάτους άνω των 2 μ.", "adapted"),

    # --- предписывающие ---
    "man_left":           ("Στροφή αριστερά μπροστά", "catalog"),
    "man_keepleft":       ("Κρατήστε αριστερά", "catalog"),
    "man_roundabout":     ("Κυκλικός κόμβος (υποχρεωτικό)", "catalog"),
    "man_minspeed":       ("Ελάχιστο όριο ταχύτητας 30", "adapted"),
    "man_pedestrians":    ("Υποχρεωτικός πεζόδρομος", "catalog"),
    "man_cycles":         ("Υποχρεωτικός ποδηλατόδρομος", "adapted"),

    # --- информационные ---
    "info_parking":       ("Στάθμευση", "catalog"),
    "info_hospital":      ("Νοσοκομείο", "new"),
    "info_oneway":        ("Μονόδρομος", "catalog"),
    "info_deadend":       ("Αδιέξοδο", "adapted"),
    "info_motorway":      ("Αυτοκινητόδρομος", "catalog"),
    "info_busstop":       ("Στάση λεωφορείου", "catalog"),

    # --- разметка ---
    "mark_double_solid":  ("Διπλή συνεχής γραμμή", "adapted"),
    "mark_solid_broken":  ("Συνεχής και διακεκομμένη γραμμή", "adapted"),
    "mark_broken":        ("Διακεκομμένη διαχωριστική γραμμή", "adapted"),
    "mark_hazard":        ("Προειδοποιητική γραμμή κινδύνου", "new"),
    "mark_double_yellow": ("Διπλή συνεχής κίτρινη γραμμή", "adapted"),
    "mark_single_yellow": ("Μονή κίτρινη γραμμή", "adapted"),
    "mark_zigzag":        ("Γραμμές ζιγκ-ζαγκ", "adapted"),
    "mark_stopline":      ("Γραμμή στάσης", "new"),
    "mark_givewayline":   ("Γραμμή παραχώρησης προτεραιότητας", "new"),
    "mark_boxjunction":   ("Κίτρινο πλέγμα στη διασταύρωση", "new"),
    "mark_lanearrows":    ("Βέλη επιλογής λωρίδας", "new"),
    "mark_zebra":         ("Διάβαση πεζών (ζέβρα)", "adapted"),

    # --- сигналы светофора (в каталоге отсутствуют) ---
    "light_red":          ("Ερυθρό φως", "new"),
    "light_redamber":     ("Ερυθρό και κίτρινο φως", "new"),
    "light_green":        ("Πράσινο φως", "new"),
    "light_amber":        ("Κίτρινο φως", "new"),
    "light_greenarrow":   ("Πράσινο βέλος", "new"),

    # --- сигналы регулировщика ---
    "warden_up":          ("Στάση για όλες τις κατευθύνσεις", "adapted"),
    "warden_side":        ("Στάση για την κυκλοφορία από μπροστά", "catalog"),
    "warden_both":        ("Στάση για την κυκλοφορία από μπροστά και από πίσω", "catalog"),
    "warden_beckon":      ("Προχώρα για την κυκλοφορία από μπροστά", "catalog"),
}


def main():
    with open(DATA, encoding="utf-8") as f:
        data = json.load(f)

    cards = data["cards"]
    ids = {c["id"] for c in cards}

    unknown = sorted(set(NAMES) - ids)
    missing = sorted(ids - set(NAMES))
    if unknown:
        print(f"В таблице есть id, которых нет в колоде: {unknown}", file=sys.stderr)
    if missing:
        print(f"Нет греческого названия для: {missing}", file=sys.stderr)
    if unknown or missing:
        sys.exit(1)

    stats = {}
    for card in cards:
        name_el, origin = NAMES[card["id"]]
        card["name_el"] = name_el
        stats[origin] = stats.get(origin, 0) + 1

    duplicates = len(cards) - len({c["name_el"] for c in cards})
    print(f"проставлено name_el: {len(cards)}")
    print(f"  из каталога: {stats.get('catalog', 0)}, "
          f"адаптировано: {stats.get('adapted', 0)}, составлено: {stats.get('new', 0)}")
    print(f"  повторяющихся названий: {duplicates}")

    if DRY_RUN:
        print("--dry-run: файл не изменён")
        return

    with open(DATA, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"записано: {DATA}")


if __name__ == "__main__":
    main()
