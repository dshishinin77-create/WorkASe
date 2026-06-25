import os
import sys
import json
import math
import ezdxf


def get_script_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def find_dwg_file(current_dir):
    files = [f for f in os.listdir(current_dir) if f.lower().endswith('.dwg')]
    if not files:
        print("Ошибка: В папке не найдено файлов .dwg")
        return None
    return os.path.join(current_dir, files[0])


def get_distance(p1, p2):
    """Считает расстояние между двумя точками на плоскости"""
    return math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)


def is_point_on_block(point, block_pos, threshold=5.0):
    """
    Проверяет, привязана ли точка линии к блоку.
    threshold — радиус «зоны фиксации» в единицах чертежа (можно подкрутить).
    """
    return get_distance(point, block_pos) <= threshold


def parse_smart_dwg(dwg_path):
    print(f"Анализирую топологию схемы: {os.path.basename(dwg_path)}...")
    try:
        doc = ezdxf.readfile(dwg_path)
    except Exception as e:
        print(f"Ошибка чтения файла: {e}")
        return None

    msp = doc.modelspace()

    blocks = []
    lines = []

    # ШАГ 1: Собираем все компоненты (Блоки)
    for element in msp.query('INSERT'):
        block_id = element.dxf.handle  # Уникальный ID элемента в DWG
        block_name = element.dxf.name
        pos = (round(element.dxf.insert.x, 2), round(element.dxf.insert.y, 2))

        attributes = {}
        if element.has_attribs:
            for attrib in element.attribs:
                tag = attrib.dxf.tag.strip()
                val = attrib.dxf.value.strip()
                if val:
                    attributes[tag] = val

        # Генерируем имя для отображения (предпочтительно ТЕГ)
        display_name = attributes.get('TAG',
                                      attributes.get('COMP_GUID', block_name))

        blocks.append({
            "id": block_id,
            "name": display_name,
            "type": block_name,
            "position": {"x": pos[0], "y": pos[1]},
            "attributes": attributes,
            "connected_lines": []  # Сюда запишем связи
        })

    # ШАГ 2: Собираем все линии связи (LINE и POLYLINE)
    # Обрабатываем обычные линии (LINE)
    for line in msp.query('LINE'):
        start = (round(line.dxf.start.x, 2), round(line.dxf.start.y, 2))
        end = (round(line.dxf.end.x, 2), round(line.dxf.end.y, 2))
        lines.append({"id": line.dxf.handle, "layer": line.dxf.layer,
                      "points": [start, end]})

    # Обрабатываем полилинии (LWPOLYLINE) - из них часто состоят трассы сигналов
    for pline in msp.query('LWPOLYLINE'):
        points = [(round(p[0], 2), round(p[1], 2)) for p in pline.get_points()]
        if len(points) >= 2:
            lines.append({"id": pline.dxf.handle, "layer": pline.dxf.layer,
                          "points": points})

    print(f"Найдено компонентов: {len(blocks)}, Линий связи: {len(lines)}")

    # ШАГ 3: Магический геометрический парсинг (Связывание интерфейсов)
    print("Восстанавливаю логические связи портов...")
    linked_lines_count = 0

    for line in lines:
        start_pt = line["points"][0]
        end_pt = line["points"][-1]

        connected_start = None
        connected_end = None

        # Ищем, к каким блокам привязаны начало и конец линии
        for b in blocks:
            b_pos = (b["position"]["x"], b["position"]["y"])

            if not connected_start and is_point_on_block(start_pt, b_pos):
                connected_start = {"block_id": b["id"],
                                   "block_name": b["name"]}
                b["connected_lines"].append(
                    {"line_id": line["id"], "role": "source/start",
                     "layer": line["layer"]})

            if not connected_end and is_point_on_block(end_pt, b_pos):
                connected_end = {"block_id": b["id"], "block_name": b["name"]}
                b["connected_lines"].append(
                    {"line_id": line["id"], "role": "target/end",
                     "layer": line["layer"]})

        if connected_start or connected_end:
            line["connections"] = {"from": connected_start, "to": connected_end}
            linked_lines_count += 1

    print(f"Топология восстановлена! Связано трасс: {linked_lines_count}")

    # Возвращаем финальную сборку для твоего редактора
    return {
        "schema_meta": {"source_file": os.path.basename(dwg_path)},
        "components": blocks,
        "connections_map": lines
    }

def main():
    current_dir = get_script_dir()
    dwg_path = find_dwg_file(current_dir)

    if not dwg_path:
        input("\nПоложите .dwg файл в папку со скриптом и нажмите Enter...")
        return

    result = parse_smart_dwg(dwg_path)

    if result:
        base_name = os.path.splitext(os.path.basename(dwg_path))[0]
        output_filename = f"{base_name}_topology.json"
        output_path = os.path.join(current_dir, output_filename)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=4)

        print(f"\n[УСПЕХ] Файл топологии сохранен: {output_filename}")

    input("\nНажмите Enter для выхода...")

if __name__ == "__main__":
    main()