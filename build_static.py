#!/usr/bin/env python3
"""
Script para generar archivos estáticos para GitHub Pages.
Este script toma el catálogo completo de Python y genera archivos JavaScript
que pueden ser servidos estáticamente.
"""

import json
import os
from pathlib import Path

def load_json_file(file_path):
    """Cargar archivo JSON"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def generate_catalog_js(catalog_data, output_path):
    """Generar archivo JavaScript con el catálogo completo"""
    js_content = f"""// Catálogo completo generado automáticamente
export const CATALOG = {json.dumps(catalog_data, ensure_ascii=False, indent=2)};
"""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(js_content)

def generate_dictionaries_js(dictionaries_dir, output_path):
    """Generar archivo JavaScript con todos los diccionarios"""
    dictionaries = {}
    
    # Cargar todos los archivos JSON de diccionarios
    for json_file in dictionaries_dir.glob('*.json'):
        name = json_file.stem
        dictionaries[name.upper()] = load_json_file(json_file)
    
    js_content = f"""// Diccionarios generados automáticamente
export const CATEGORIES = {json.dumps(dictionaries.get('CATEGORIES', {}), ensure_ascii=False, indent=2)};
export const INGREDIENTS = {json.dumps(dictionaries.get('INGREDIENTS', {}), ensure_ascii=False, indent=2)};
export const DIETS = {json.dumps(dictionaries.get('DIETS', {}), ensure_ascii=False, indent=2)};
export const ALLERGENS = {json.dumps(dictionaries.get('ALLERGENS', {}), ensure_ascii=False, indent=2)};
export const HEALTH = {json.dumps(dictionaries.get('HEALTH', {}), ensure_ascii=False, indent=2)};
export const INTENTS = {json.dumps(dictionaries.get('INTENTS', {}), ensure_ascii=False, indent=2)};
"""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(js_content)

def main():
    """Función principal"""
    # Rutas
    app_dir = Path(__file__).parent / "app"
    data_dir = app_dir / "data"
    dictionaries_dir = data_dir / "dictionaries"
    web_dir = app_dir / "web"
    
    # Cargar catálogo completo
    catalog_path = data_dir / "catalog.json"
    catalog_data = load_json_file(catalog_path)
    
    print(f"Generando archivos estáticos...")
    print(f"Catálogo: {len(catalog_data)} platos")
    
    # Generar archivos JavaScript
    generate_catalog_js(catalog_data, web_dir / "data" / "catalog.js")
    generate_dictionaries_js(dictionaries_dir, web_dir / "data" / "dictionaries.js")
    
    print("✅ Archivos estáticos generados exitosamente")
    print(f"📁 Catálogo: {web_dir / 'data' / 'catalog.js'}")
    print(f"📁 Diccionarios: {web_dir / 'data' / 'dictionaries.js'}")

if __name__ == "__main__":
    main()
