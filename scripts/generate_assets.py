#!/usr/bin/env python3
"""Generate SVG assets and signs.json for the Cyprus road signs Telegram bot."""
import json
import os

OUT_SVG = os.path.join(os.path.dirname(__file__), "..", "assets", "svg")
OUT_DATA = os.path.join(os.path.dirname(__file__), "..", "data")

R = "#C8102E"; B = "#0057A8"; K = "#1a1a1a"; Y = "#F5C518"; W = "#ffffff"
A = "#4a4a46"; YY = "#F2C10E"; G = "#1D9E75"
N = 'stroke-width="0"'

def svg(inner, vb="0 0 100 100"):
    return f'<svg viewBox="{vb}" xmlns="http://www.w3.org/2000/svg">{inner}</svg>'

def tri(p):
    return svg(f'<path d="M50 10 L95 86 L5 86 Z" fill="{W}" stroke="{R}" stroke-width="9" stroke-linejoin="round"/><g fill="{K}" stroke="{K}">{p}</g>')

def pro(p):
    return svg(f'<circle cx="50" cy="50" r="41" fill="{W}" stroke="{R}" stroke-width="10"/><g fill="{K}" stroke="{K}">{p}</g>')

def man(p):
    return svg(f'<circle cx="50" cy="50" r="46" fill="{B}"/><g fill="{W}" stroke="{W}">{p}</g>')

def inf(p):
    return svg(f'<rect x="6" y="6" width="88" height="88" rx="6" fill="{B}"/><g fill="{W}" stroke="{W}">{p}</g>')

def road(inner):
    return svg(f'<rect x="0" y="0" width="120" height="84" rx="6" fill="{A}"/>{inner}', "0 0 120 84")

def lamp(on, arrow=False):
    c = ["#3a3a38", "#3a3a38", "#3a3a38"]
    for i in on:
        c[i] = [R, YY, G][i]
    g = f'<rect x="32" y="6" width="36" height="88" rx="7" fill="#22221f"/>'
    g += f'<circle cx="50" cy="26" r="11" fill="{c[0]}"/><circle cx="50" cy="50" r="11" fill="{c[1]}"/>'
    if arrow:
        g += f'<path d="M42 62 L42 56 L56 56 L56 50 L64 59 L56 68 L56 62 Z" fill="{G}"/>'
    else:
        g += f'<circle cx="50" cy="74" r="11" fill="{c[2]}"/>'
    return svg(g)

def ped(body):
    return svg(
        f'<rect x="0" y="0" width="100" height="100" rx="6" fill="#eceae4"/>'
        f'<g stroke="{K}" stroke-width="5" stroke-linecap="round" fill="none">{body}</g>'
        f'<circle cx="50" cy="24" r="9" fill="{K}"/><path d="M40 18 q10 -8 20 0 z" fill="{K}"/>'
    )

# id, category, name_ru, name_en, explanation_ru, svg_content
CARDS = [
    # --- warning ---
    ("warn_bend_right", "warning", "Опасный поворот направо", "Right hand bend",
     "Снизьте скорость перед поворотом.",
     tri(f'<path d="M50 78 L50 56 Q50 40 62 36 L60 44 L74 33 L58 26 L60 34 Q42 39 42 58 L42 78 Z" {N}/>')),
    ("warn_crossroads", "warning", "Перекрёсток", "Crossroads",
     "Впереди пересечение равнозначных дорог.",
     tri(f'<rect x="46" y="34" width="8" height="44" {N}/><rect x="28" y="50" width="44" height="8" {N}/>')),
    ("warn_roundabout", "warning", "Впереди круговое движение", "Roundabout ahead",
     "Приоритет у тех, кто уже на круге.",
     tri(f'<path d="M50 34 a20 20 0 1 0 20 20" fill="none" stroke-width="7"/><path d="M44 30 L58 36 L44 42 Z" {N}/>')),
    ("warn_zebra", "warning", "Пешеходный переход", "Zebra crossing",
     "Будьте готовы пропустить пешеходов.",
     tri(f'<circle cx="52" cy="40" r="5" {N}/><path d="M52 46 L52 62 M52 62 L45 76 M52 62 L59 76 M44 50 L60 50" stroke-width="4" fill="none" stroke-linecap="round"/><path d="M30 82 L70 82" stroke-width="3"/>')),
    ("warn_children", "warning", "Дети, школа рядом", "Children ahead",
     "Возможен внезапный выход детей на дорогу.",
     tri(f'<circle cx="42" cy="42" r="5" {N}/><path d="M42 48 L42 62 L36 76 M42 62 L48 76 M35 52 L49 52" stroke-width="4" fill="none" stroke-linecap="round"/><circle cx="60" cy="46" r="4" {N}/><path d="M60 51 L60 63 L55 75 M60 63 L65 75" stroke-width="3.5" fill="none" stroke-linecap="round"/>')),
    ("warn_roadworks", "warning", "Дорожные работы", "Road works",
     "Возможны рабочие и техника на проезжей части.",
     tri(f'<circle cx="46" cy="40" r="5" {N}/><path d="M46 46 L46 60 L40 76 M46 60 L54 74" stroke-width="4" fill="none" stroke-linecap="round"/><path d="M44 50 L66 40" stroke-width="4"/><rect x="62" y="34" width="10" height="7" {N} transform="rotate(-25 67 37)"/><path d="M30 82 L70 82" stroke-width="3"/>')),
    ("warn_slippery", "warning", "Скользкая дорога", "Slippery road",
     "Избегайте резких манёвров и торможения.",
     tri(f'<rect x="38" y="36" width="24" height="16" rx="3" {N}/><path d="M28 74 q10 -10 20 0 q10 10 22 -2" fill="none" stroke-width="5" stroke-linecap="round"/><path d="M30 60 q6 -6 12 0" fill="none" stroke-width="4"/>')),
    ("warn_descent", "warning", "Крутой спуск", "Steep descent",
     "Тормозите двигателем, следите за скоростью.",
     tri(f'<path d="M22 44 L78 78 L22 78 Z" {N}/>')),
    ("warn_narrows", "warning", "Сужение дороги", "Road narrows",
     "Дорога сужается с обеих сторон.",
     tri('<path d="M30 80 L38 44" stroke-width="6" fill="none"/><path d="M70 80 L62 44" stroke-width="6" fill="none"/>')),
    ("warn_signals", "warning", "Впереди светофор", "Traffic signals",
     "Приготовьтесь к возможной остановке.",
     tri('<rect x="41" y="30" width="18" height="42" rx="4" fill="none" stroke-width="4"/><circle cx="50" cy="40" r="4.5"/><circle cx="50" cy="51" r="4.5"/><circle cx="50" cy="62" r="4.5"/><path d="M50 72 L50 82" stroke-width="4"/>')),
    ("warn_animals", "warning", "Дикие животные", "Wild animals",
     "Возможен выход животных на дорогу.",
     tri(f'<path d="M36 58 Q42 48 54 48 L64 48 L68 52 L64 56 L62 74 L58 74 L60 58 L44 58 L42 74 L38 74 Z" {N}/><path d="M64 48 L60 38 M68 50 L72 40" stroke-width="3" fill="none"/>')),
    ("warn_giveway_ahead", "warning", "Впереди «Уступи дорогу»", "Give way ahead",
     "Через 200 м знак «Уступите дорогу».",
     tri('<path d="M32 44 L68 44 L50 76 Z" fill="none" stroke-width="6" stroke-linejoin="round"/>')),
    ("warn_hump", "warning", "Искусственная неровность", "Speed hump",
     "Снизьте скорость перед «лежачим полицейским».",
     tri('<path d="M26 74 L74 74" stroke-width="5"/><path d="M34 74 q16 -22 32 0" fill="none" stroke-width="6"/>')),
    ("warn_rocks", "warning", "Камнепад", "Falling rocks",
     "Возможны камни на проезжей части.",
     tri(f'<path d="M40 30 L40 78 L34 78 L34 30 Z" {N}/><circle cx="52" cy="52" r="6" {N}/><circle cx="64" cy="66" r="5" {N}/><circle cx="50" cy="72" r="4" {N}/>')),
    # --- priority ---
    ("prio_stop", "priority", "Стоп, обязательная остановка", "Stop",
     "Полная остановка обязательна, даже если дорога свободна.",
     svg(f'<path d="M32 8 L68 8 L92 32 L92 68 L68 92 L32 92 L8 68 L8 32 Z" fill="{R}"/><text x="50" y="60" text-anchor="middle" font-family="Arial,sans-serif" font-size="26" font-weight="bold" fill="{W}">STOP</text>')),
    ("prio_giveway", "priority", "Уступите дорогу", "Give way",
     "Пропустите транспорт на пересекаемой дороге.",
     svg(f'<path d="M50 92 L4 12 L96 12 Z" fill="{W}" stroke="{R}" stroke-width="10" stroke-linejoin="round"/>')),
    ("prio_main", "priority", "Главная дорога", "Priority road",
     "У вас приоритет на перекрёстках.",
     svg(f'<path d="M50 6 L94 50 L50 94 L6 50 Z" fill="{Y}" stroke="{W}" stroke-width="8" stroke-linejoin="round"/>')),
    ("prio_main_end", "priority", "Конец главной дороги", "End of priority",
     "Приоритет закончился.",
     svg(f'<path d="M50 6 L94 50 L50 94 L6 50 Z" fill="{Y}" stroke="{W}" stroke-width="8" stroke-linejoin="round"/><path d="M20 80 L80 20" stroke="{K}" stroke-width="6"/>')),
    # --- prohibitory ---
    ("proh_noentry", "prohibitory", "Въезд запрещён", "No entry",
     "Движение в этом направлении запрещено для всех ТС.",
     svg(f'<circle cx="50" cy="50" r="46" fill="{R}"/><rect x="20" y="43" width="60" height="14" rx="2" fill="{W}"/>')),
    ("proh_speed50", "prohibitory", "Ограничение скорости 50", "Speed limit 50",
     "Не превышайте 50 км/ч.",
     pro(f'<text x="50" y="63" text-anchor="middle" font-family="Arial,sans-serif" font-size="38" font-weight="bold" fill="{K}" stroke="none">50</text>')),
    ("proh_speed_end", "prohibitory", "Конец ограничения скорости", "End of speed limit",
     "Действует общее ограничение для данного типа дороги.",
     svg(f'<circle cx="50" cy="50" r="41" fill="{W}" stroke="#888" stroke-width="7"/><text x="50" y="63" text-anchor="middle" font-family="Arial,sans-serif" font-size="36" font-weight="bold" fill="#888">50</text><path d="M22 78 L78 22" stroke="#555" stroke-width="6"/>')),
    ("proh_overtake", "prohibitory", "Обгон запрещён", "No overtaking",
     "Обгон механических ТС запрещён.",
     pro(f'<path d="M30 40 h16 v34 h-16 z" fill="{K}" {N}/><path d="M54 40 h16 v34 h-16 z" fill="{R}" {N}/><path d="M38 28 v10 M62 28 v10" stroke-width="4"/>')),
    ("proh_nowaiting", "prohibitory", "Стоянка запрещена", "No waiting",
     "Остановиться для посадки/высадки можно, стоять нельзя.",
     svg(f'<circle cx="50" cy="50" r="46" fill="{B}"/><circle cx="50" cy="50" r="41" fill="none" stroke="{R}" stroke-width="9"/><path d="M24 76 L76 24" stroke="{R}" stroke-width="9"/>')),
    ("proh_nostopping", "prohibitory", "Остановка запрещена", "No stopping",
     "Запрещена даже кратковременная остановка.",
     svg(f'<circle cx="50" cy="50" r="46" fill="{B}"/><circle cx="50" cy="50" r="41" fill="none" stroke="{R}" stroke-width="9"/><path d="M24 76 L76 24 M24 24 L76 76" stroke="{R}" stroke-width="9"/>')),
    ("proh_nouturn", "prohibitory", "Разворот запрещён", "No U-turn",
     "Разворот на данном участке запрещён.",
     pro(f'<path d="M62 76 L62 44 a12 12 0 0 0 -24 0 L38 60" fill="none" stroke-width="7"/><path d="M30 58 L46 58 L38 76 Z" {N}/>')),
    ("proh_noleft", "prohibitory", "Поворот налево запрещён", "No left turn",
     "Поворот налево запрещён, разворот обычно тоже.",
     pro(f'<path d="M64 76 L64 46 L38 46" fill="none" stroke-width="7"/><path d="M40 32 L40 60 L22 46 Z" {N}/><path d="M20 80 L80 20" stroke="{R}" stroke-width="8"/>')),
    ("proh_nohorn", "prohibitory", "Звуковой сигнал запрещён", "No horn",
     "Сигналить можно только для предотвращения ДТП.",
     pro(f'<path d="M30 44 L44 44 L58 32 L58 68 L44 56 L30 56 Z" {N}/><path d="M66 40 q8 10 0 20 M74 34 q12 16 0 32" fill="none" stroke-width="4"/>')),
    ("proh_nomotor", "prohibitory", "Движение механических ТС запрещено", "No motor vehicles",
     "Запрет для автомобилей и мотоциклов.",
     pro(f'<path d="M18 62 h34 v-10 h-34 z M22 52 l6 -9 h18 v9" {N}/><circle cx="27" cy="66" r="5" {N}/><circle cx="46" cy="66" r="5" {N}/><circle cx="62" cy="66" r="6" fill="none" stroke-width="3"/><circle cx="80" cy="66" r="6" fill="none" stroke-width="3"/><path d="M62 66 L70 48 L76 48 M70 48 L80 66" fill="none" stroke-width="3"/>')),
    ("proh_height", "prohibitory", "Ограничение высоты 3,8 м", "Max height 3.8 m",
     "Проезд ТС выше 3,8 м запрещён.",
     pro(f'<path d="M24 28 L24 72 M76 28 L76 72" stroke-width="5"/><path d="M32 50 L68 50" stroke-width="4"/><path d="M24 50 L36 44 L36 56 Z" {N}/><path d="M76 50 L64 44 L64 56 Z" {N}/><text x="50" y="72" text-anchor="middle" font-family="Arial,sans-serif" font-size="17" font-weight="bold" fill="{K}" stroke="none">3.8m</text>')),
    ("proh_width", "prohibitory", "Ограничение ширины 2 м", "Max width 2 m",
     "Проезд ТС шире 2 м запрещён.",
     pro(f'<path d="M28 24 L28 76 M72 24 L72 76" stroke-width="5"/><path d="M28 50 L72 50" stroke-width="4"/><text x="50" y="70" text-anchor="middle" font-family="Arial,sans-serif" font-size="18" font-weight="bold" fill="{K}" stroke="none">2m</text>')),
    # --- mandatory ---
    ("man_left", "mandatory", "Движение налево", "Turn left ahead",
     "Обязательный поворот налево.",
     man(f'<path d="M60 78 L60 48 L36 48" fill="none" stroke-width="8"/><path d="M40 30 L40 66 L18 48 Z" {N}/>')),
    ("man_keepleft", "mandatory", "Держитесь левее", "Keep left",
     "Объезжайте препятствие слева.",
     man(f'<path d="M66 20 L66 80 L54 80 L54 44 L28 44 L28 32 L54 32 Z" {N} fill="{W}"/><path d="M30 38 L14 38 L26 26 M26 50 L14 38" fill="none" stroke-width="7"/>')),
    ("man_roundabout", "mandatory", "Круговое движение", "Roundabout",
     "Движение по кругу по часовой стрелке (левостороннее движение).",
     man(f'<path d="M50 24 a26 26 0 1 1 -18 44" fill="none" stroke-width="8"/><path d="M56 18 L40 26 L54 36 Z" {N}/>')),
    ("man_minspeed", "mandatory", "Минимальная скорость 30", "Minimum speed 30",
     "Ехать медленнее 30 км/ч запрещено.",
     man(f'<text x="50" y="64" text-anchor="middle" font-family="Arial,sans-serif" font-size="38" font-weight="bold" fill="{W}" stroke="none">30</text>')),
    ("man_pedestrians", "mandatory", "Дорожка для пешеходов", "Pedestrians only",
     "Только для пешеходов.",
     man(f'<circle cx="50" cy="26" r="8" {N}/><path d="M50 36 L50 60 M50 60 L40 82 M50 60 L60 82 M36 46 L64 46" fill="none" stroke-width="6" stroke-linecap="round"/>')),
    ("man_cycles", "mandatory", "Дорожка для велосипедистов", "Cycle route only",
     "Только для велосипедов.",
     man(f'<circle cx="28" cy="62" r="14" fill="none" stroke-width="5"/><circle cx="72" cy="62" r="14" fill="none" stroke-width="5"/><path d="M28 62 L44 62 L56 36 L64 36 M44 62 L60 36 M56 36 L72 62" fill="none" stroke-width="5"/><circle cx="60" cy="24" r="6" {N}/>')),
    # --- info ---
    ("info_parking", "info", "Парковка", "Parking",
     "Разрешённое место стоянки.",
     inf(f'<text x="50" y="72" text-anchor="middle" font-family="Arial,sans-serif" font-size="62" font-weight="bold" fill="{W}" stroke="none">P</text>')),
    ("info_hospital", "info", "Больница", "Hospital",
     "Рядом больница: не шумите, будьте внимательны.",
     inf(f'<text x="50" y="70" text-anchor="middle" font-family="Arial,sans-serif" font-size="52" font-weight="bold" fill="{W}" stroke="none">H</text>')),
    ("info_oneway", "info", "Одностороннее движение", "One-way street",
     "Движение всей проезжей части в одном направлении.",
     inf(f'<path d="M20 50 L66 50" stroke-width="9"/><path d="M62 32 L86 50 L62 68 Z" {N}/>')),
    ("info_deadend", "info", "Тупик", "No through road",
     "Сквозного проезда нет.",
     inf(f'<rect x="44" y="36" width="12" height="42" {N}/><rect x="30" y="26" width="40" height="10" fill="{R}" {N}/>')),
    ("info_motorway", "info", "Автомагистраль", "Motorway",
     "Начало автомагистрали: макс. 100, мин. 65 км/ч.",
     inf('<path d="M22 84 L38 20 L46 20 L34 84 Z"/><path d="M78 84 L62 20 L54 20 L66 84 Z"/><path d="M48 30 L52 30 M48 48 L52 48 M48 66 L52 66" stroke-width="6"/>')),
    ("info_busstop", "info", "Остановка автобуса", "Bus stop",
     "Место остановки маршрутного транспорта.",
     inf(f'<rect x="24" y="24" width="52" height="44" rx="6" fill="none" stroke-width="5"/><rect x="30" y="32" width="40" height="16" {N}/><circle cx="36" cy="60" r="5" {N}/><circle cx="64" cy="60" r="5" {N}/><path d="M28 76 L72 76" stroke-width="5"/>')),
    # --- markings ---
    ("mark_double_solid", "marking", "Двойная сплошная", "Double white line",
     "Пересекать и обгонять нельзя ни с одной стороны.",
     road(f'<path d="M54 0 L54 84 M66 0 L66 84" stroke="{W}" stroke-width="5"/>')),
    ("mark_solid_broken", "marking", "Сплошная и прерывистая", "Solid and broken line",
     "Ориентируйтесь на ближнюю к вам линию: сплошную пересекать нельзя.",
     road(f'<path d="M54 0 L54 84" stroke="{W}" stroke-width="5"/><path d="M66 2 L66 16 M66 26 L66 40 M66 50 L66 64 M66 74 L66 84" stroke="{W}" stroke-width="5"/>')),
    ("mark_broken", "marking", "Прерывистая осевая", "Broken centre line",
     "Обгон и пересечение разрешены, если безопасно.",
     road(f'<path d="M60 2 L60 18 M60 32 L60 48 M60 62 L60 82" stroke="{W}" stroke-width="5"/>')),
    ("mark_hazard", "marking", "Удлинённая прерывистая", "Hazard warning line",
     "Предупреждение об опасности: не пересекайте без необходимости.",
     road(f'<path d="M60 2 L60 26 M60 34 L60 58 M60 66 L60 84" stroke="{W}" stroke-width="6"/>')),
    ("mark_double_yellow", "marking", "Двойная жёлтая у обочины", "Double yellow lines",
     "Остановка и стоянка запрещены в любое время.",
     road(f'<rect x="0" y="60" width="120" height="24" fill="#6b6b66"/><path d="M0 58 L120 58 M0 66 L120 66" stroke="{YY}" stroke-width="4"/>')),
    ("mark_single_yellow", "marking", "Одинарная жёлтая у обочины", "Single yellow line",
     "Стоянка запрещена в часы, указанные на табличке.",
     road(f'<rect x="0" y="60" width="120" height="24" fill="#6b6b66"/><path d="M0 58 L120 58" stroke="{YY}" stroke-width="4"/>')),
    ("mark_zigzag", "marking", "Зигзаг у перехода", "Zigzag lines",
     "Нельзя стоять и обгонять на подходе к переходу.",
     road(f'<path d="M8 74 L20 58 L32 74 L44 58 L56 74 L68 58 L80 74 L92 58 L104 74 L112 62" stroke="{YY}" stroke-width="4" fill="none"/>')),
    ("mark_stopline", "marking", "Стоп-линия", "Stop line",
     "Полная остановка перед линией, даже если дорога свободна.",
     road(f'<path d="M6 46 L114 46" stroke="{W}" stroke-width="9"/><path d="M40 60 L40 82 M80 60 L80 82" stroke="{W}" stroke-width="4"/>')),
    ("mark_givewayline", "marking", "Линия «уступи дорогу»", "Give way line",
     "Двойной пунктир поперёк: пропустите тех, кто на главной.",
     road(''.join(f'<path d="M{x} 44 h10 v7 h-10 z M{x} 56 h10 v7 h-10 z" fill="{W}"/>' for x in (6, 22, 38, 54, 70, 86, 102)))),
    ("mark_boxjunction", "marking", "Жёлтая сетка на перекрёстке", "Box junction",
     "Въезжать только когда выезд свободен.",
     road(f'<path d="M6 6 h108 v72 h-108 z" fill="none" stroke="{YY}" stroke-width="4"/><path d="M6 6 L60 78 M60 6 L114 78 M60 6 L6 78 M114 6 L60 78" stroke="{YY}" stroke-width="3"/>')),
    ("mark_lanearrows", "marking", "Стрелки по полосам", "Lane arrows",
     "Полоса ведёт только в указанном направлении.",
     road(f'<path d="M34 76 L34 34 M34 26 L27 40 L41 40 Z" stroke="{W}" stroke-width="6" fill="{W}"/><path d="M84 76 L84 46 L98 46 M100 38 L112 47 L100 56 Z" stroke="{W}" stroke-width="6" fill="{W}"/>')),
    ("mark_zebra", "marking", "Зебра", "Zebra crossing",
     "Приоритет у пешехода, ступившего на переход.",
     road(''.join(f'<path d="M{x} 8 h14 v68 h-14 z" fill="{W}"/>' for x in (14, 42, 70, 98)))),
    # --- lights ---
    ("light_red", "light", "Красный", "Red light",
     "Стоп перед стоп-линией. Движение запрещено.", lamp([0])),
    ("light_redamber", "light", "Красный с жёлтым", "Red and amber",
     "Скоро зелёный, приготовьтесь. Ехать ещё нельзя.", lamp([0, 1])),
    ("light_green", "light", "Зелёный", "Green light",
     "Движение разрешено, если перекрёсток свободен.", lamp([2])),
    ("light_amber", "light", "Жёлтый", "Amber light",
     "Остановитесь, если можете сделать это безопасно.", lamp([1])),
    ("light_greenarrow", "light", "Зелёная стрелка", "Green arrow",
     "Движение разрешено только в направлении стрелки.", lamp([], True)),
    # --- warden ---
    ("warden_up", "warden", "Рука поднята вверх", "Arm raised up",
     "Стоп для всех; кто уже на перекрёстке — завершает проезд.",
     ped('<path d="M50 33 L50 62 M50 62 L40 88 M50 62 L60 88 M50 40 L34 52 M50 40 L64 20"/>')),
    ("warden_side", "warden", "Рука вытянута в сторону", "Arm extended",
     "Стоп для транспорта, приближающегося спереди.",
     ped('<path d="M50 33 L50 62 M50 62 L40 88 M50 62 L60 88 M50 40 L34 52 M50 40 L82 40"/>')),
    ("warden_both", "warden", "Обе руки в стороны", "Both arms extended",
     "Стоп спереди и сзади; поток сбоку едет.",
     ped('<path d="M50 33 L50 62 M50 62 L40 88 M50 62 L60 88 M50 40 L18 40 M50 40 L82 40"/>')),
    ("warden_beckon", "warden", "Приглашающий взмах", "Beckoning on",
     "Проезд разрешён в указанном направлении.",
     ped('<path d="M50 33 L50 62 M50 62 L40 88 M50 62 L60 88 M50 40 L34 52 M50 40 L72 30 M72 30 L64 20 M72 30 L82 34"/>')),
]

CATEGORIES = {
    "warning": {"ru": "Предупреждающие", "en": "Warning signs"},
    "priority": {"ru": "Знаки приоритета", "en": "Priority signs"},
    "prohibitory": {"ru": "Запрещающие", "en": "Prohibitory signs"},
    "mandatory": {"ru": "Предписывающие", "en": "Mandatory signs"},
    "info": {"ru": "Информационные", "en": "Information signs"},
    "marking": {"ru": "Дорожная разметка", "en": "Road markings"},
    "light": {"ru": "Сигналы светофора", "en": "Traffic lights"},
    "warden": {"ru": "Жесты регулировщика", "en": "Warden signals"},
}

def main():
    os.makedirs(OUT_SVG, exist_ok=True)
    os.makedirs(OUT_DATA, exist_ok=True)
    records = []
    for cid, cat, ru, en, expl, content in CARDS:
        path = os.path.join(OUT_SVG, f"{cid}.svg")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        records.append({
            "id": cid, "category": cat,
            "name_ru": ru, "name_en": en,
            "explanation_ru": expl,
            "svg": f"assets/svg/{cid}.svg",
            "png": f"assets/png/{cid}.png",
        })
    data = {"categories": CATEGORIES, "cards": records}
    with open(os.path.join(OUT_DATA, "signs.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"OK: {len(records)} cards, {len(CATEGORIES)} categories")

if __name__ == "__main__":
    main()
