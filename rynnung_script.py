import os
import sys
import json
import ezdxf


def get_script_dir():
    """Определяет папку, где лежит запущенный скрипт или скомпилированный .exe"""
    if getattr(sys, 'frozen', False):
        # Если запущен скомпилированный .exe
        return os.path.dirname(sys.executable)
    else:
        # Если запущен обычный .py файл
        return os.path.dirname(os.path.abspath(__file__))


def find_dwg_file(current_dir):
    """Ищет один .dwg файл в текущей директории"""
    files = [f for f in os.listdir(current_dir) if f.lower().endswith('.dwg')]
    if not files:
        print("Ошибка: В папке не найдено ни одного файла .dwg")
        return None
    if len(files) > 1:
        print(
            f"Предупреждение: Найдено несколько файлов. Взят первый: {files[0]}")
    return os.path.join(current_dir, files[0])


def parse_dwg(dwg_path):
    """Парсит DWG и собирает данные блоков и их атрибутов"""
    print(
        f"Читаю файл: {os.path.basename(dwg_path)}... Пожалуйста, подождите.")
    try:
        doc = ezdxf.readfile(dwg_path)
    except IOError:
        print(
            "Ошибка: Не удалось открыть файл (возможно, он поврежден или открыт в AutoCAD)")
        return None
    except ezdxf.DXFStructureError:
        print("Ошибка: Нарушена структура DXF/DWG файла")
        return None

    msp = doc.modelspace()
    parsed_components = []

    # Ищем все элементы вставки блоков (INSERT)
    # В них SmartPlant зашивает графические элементы и их свойства
    for element in msp.query('INSERT'):
        block_name = element.dxf.name
        insert_point = element.dxf.insert  # Координаты (X, Y, Z)

        # Собираем все атрибуты блока (интерфейсы, GUID, теги)
        attributes = {}
        if element.has_attribs:
            for attrib in element.attribs:
                # Избавляемся от лишних пробелов в начале и конце
                tag = attrib.dxf.tag.strip()
                value = attrib.dxf.value.strip()
                if value:  # Сохраняем только непустые свойства
                    attributes[tag] = value

        # Формируем структуру данных компонента
        component_data = {
            "block_name": block_name,
            "position": {
                "x": round(insert_point.x, 3),
                "y": round(insert_point.y, 3)
            },
            "attributes": attributes
        }
        parsed_components.append(component_data)

    print(f"Успешно обработано элементов: {len(parsed_components)}")
    return parsed_components


def main():
    current_dir = get_script_dir()
    dwg_path = find_dwg_file(current_dir)

    if not dwg_path:
        input("\nНажмите Enter для выхода...")
        return

    # Запускаем парсинг
    data = parse_dwg(dwg_path)

    if data:
        # Формируем имя для выходного файла (заменяем .dwg на _parsed.json)
        base_name = os.path.splitext(os.path.basename(dwg_path))[0]
        output_filename = f"{base_name}_parsed.json"
        output_path = os.path.join(current_dir, output_filename)

        # Сохраняем данные в красивом формате JSON с поддержкой кириллицы
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

        print(f"Готово! Результат сохранен в: {output_filename}")

    input("\nНажмите Enter для выхода...")


if main == "__main__":
    main()