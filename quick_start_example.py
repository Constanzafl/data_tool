#!/usr/bin/env python3
"""
Quick Start - Ejemplo simple de uso del Schema Analyzer
"""

# IMPORTANTE: Primero copia todos los archivos de las fases 1-5 en tu directorio

import sys
import os
# Importar todos los módulos anteriores
from schema_extractor import SchemaExtractor, Table
from relationship_detector import RelationshipDetector, RelationshipCandidate  
from llm_verifier import OllamaVerifier, verify_without_llm, OllamaInstaller
from dbml_generator import DBMLGenerator, DBMLEnhancer

def check_dependencies():
    """Verifica que las dependencias estén instaladas"""
    required = ['pandas', 'numpy', 'sklearn', 'sentence_transformers', 'requests']
    missing = []
    
    for module in required:
        try:
            __import__(module)
        except ImportError:
            missing.append(module)
    
    if missing:
        print("❌ Faltan dependencias. Instala con:")
        print("pip install pandas numpy scikit-learn sentence-transformers requests psycopg2-binary tqdm")
        sys.exit(1)
    
    print("✅ Todas las dependencias están instaladas")

def create_sample_database():
    """Crea una base de datos SQLite de ejemplo para testing"""
    import sqlite3
    
    print("\n📦 Creando base de datos de ejemplo...")
    
    conn = sqlite3.connect('example_store.db')
    cursor = conn.cursor()
    
    # Crear tablas
    cursor.executescript("""
    -- Tabla de clientes
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name VARCHAR(100) NOT NULL,
        email VARCHAR(100) UNIQUE NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    -- Tabla de productos
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name VARCHAR(100) NOT NULL,
        price DECIMAL(10,2) NOT NULL,
        category_id INTEGER,
        stock INTEGER DEFAULT 0
    );
    
    -- Tabla de categorías (sin FK explícita)
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name VARCHAR(50) NOT NULL,
        description TEXT
    );
    
    -- Tabla de órdenes
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        total DECIMAL(10,2),
        FOREIGN KEY (customer_id) REFERENCES customers(id)
    );
    
    -- Tabla de detalles de orden (sin FKs explícitas)
    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        price DECIMAL(10,2) NOT NULL
    );
    
    -- Insertar datos de ejemplo
    INSERT OR IGNORE INTO customers (name, email) VALUES 
        ('Juan Pérez', 'juan@email.com'),
        ('María García', 'maria@email.com'),
        ('Carlos López', 'carlos@email.com');
    
    INSERT OR IGNORE INTO categories (name, description) VALUES
        ('Electrónica', 'Productos electrónicos'),
        ('Ropa', 'Vestimenta y accesorios'),
        ('Alimentos', 'Productos alimenticios');
    
    INSERT OR IGNORE INTO products (name, price, category_id, stock) VALUES
        ('Laptop HP', 899.99, 1, 10),
        ('Mouse Logitech', 29.99, 1, 50),
        ('Camiseta Nike', 39.99, 2, 30),
        ('Jeans Levis', 79.99, 2, 20),
        ('Café Premium', 12.99, 3, 100);
    
    INSERT OR IGNORE INTO orders (customer_id, total) VALUES
        (1, 929.98),
        (2, 119.98),
        (1, 39.99);
    
    INSERT OR IGNORE INTO order_items (order_id, product_id, quantity, price) VALUES
        (1, 1, 1, 899.99),
        (1, 2, 1, 29.99),
        (2, 3, 1, 39.99),
        (2, 4, 1, 79.99),
        (3, 3, 1, 39.99);
    """)
    
    conn.commit()
    conn.close()
    
    print("✅ Base de datos de ejemplo creada: example_store.db")

def run_basic_analysis():
    """Ejecuta un análisis básico sin LLM"""
    from complete_schema_analyzer import SchemaAnalyzer
    
    print("\n🔍 Ejecutando análisis básico (sin LLM)...")
    
    analyzer = SchemaAnalyzer(
        db_type="sqlite",
        connection_params={"database": "example_store.db"},
        use_llm=False  # No requiere Ollama
    )
    
    results = analyzer.analyze_complete(
        output_dir="./output_basic",
        sample_size=3,
        max_llm_verifications=0
    )
    
    return results

def run_advanced_analysis():
    """Ejecuta análisis completo con LLM"""
    from complete_schema_analyzer import SchemaAnalyzer
    
    print("\n🤖 Ejecutando análisis avanzado (con LLM)...")
    
    try:
        analyzer = SchemaAnalyzer(
            db_type="sqlite",
            connection_params={"database": "example_store.db"},
            use_llm=True,
            llm_model="llama2"
        )
        
        results = analyzer.analyze_complete(
            output_dir="./output_advanced",
            sample_size=5,
            max_llm_verifications=5
        )
        
        return results
    
    except Exception as e:
        print(f"⚠️  Error con LLM: {e}")
        print("💡 Ejecuta el análisis básico sin LLM en su lugar")
        return None

def main():
    """Función principal"""
    print("🚀 SCHEMA ANALYZER - Quick Start")
    print("="*50)
    
    # 1. Verificar dependencias
    check_dependencies()
    
    # 2. Crear base de datos de ejemplo
    create_sample_database()
    
    # 3. Menú de opciones
    print("\n¿Qué tipo de análisis deseas ejecutar?")
    print("1. Análisis básico (sin LLM) - Rápido y no requiere Ollama")
    print("2. Análisis avanzado (con LLM) - Requiere Ollama instalado")
    print("3. Ambos análisis")
    
    choice = input("\nElige una opción (1-3): ").strip()
    
    if choice == "1" or choice == "3":
        run_basic_analysis()
    
    if choice == "2" or choice == "3":
        run_advanced_analysis()
    
    if choice not in ["1", "2", "3"]:
        print("❌ Opción no válida")
        return
    
    print("\n✨ ¡Análisis completado!")
    print("\n📁 Revisa los archivos generados en:")
    print("   - ./output_basic/   (análisis sin LLM)")
    print("   - ./output_advanced/ (análisis con LLM)")
    print("\n🎨 Para visualizar el diagrama:")
    print("   1. Abre el archivo .dbml generado")
    print("   2. Copia el contenido")
    print("   3. Pégalo en https://dbdiagram.io/d")

if __name__ == "__main__":
    main()