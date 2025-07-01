"""
Fase 5: Integración Completa - Schema Analyzer
Herramienta completa para análisis de esquemas y generación de diagramas ER
"""

import os
import json
from typing import Dict, List, Optional, Tuple
import pandas as pd
from datetime import datetime

# Importar todos los módulos anteriores
from schema_extractor import SchemaExtractor, Table
from relationship_detector import RelationshipDetector, RelationshipCandidate  
from llm_verifier import OllamaVerifier, verify_without_llm, OllamaInstaller
from dbml_generator import DBMLGenerator, DBMLEnhancer

class SchemaAnalyzer:
    """
    Clase principal que integra todas las fases del análisis
    """
    
    def __init__(self, 
                 db_type: str = "sqlite",
                 connection_params: dict = None,
                 use_llm: bool = True,
                 llm_model: str = "llama2"):
        """
        Inicializa el analizador completo
        
        Args:
            db_type: Tipo de base de datos ("sqlite" o "postgresql")
            connection_params: Parámetros de conexión
            use_llm: Si usar verificación con LLM
            llm_model: Modelo de Ollama a usar
        """
        self.db_type = db_type
        self.connection_params = connection_params or {}
        self.use_llm = use_llm
        self.llm_model = llm_model
        
        # Inicializar componentes
        self.extractor = SchemaExtractor(db_type, connection_params)
        self.detector = RelationshipDetector()
        self.generator = DBMLGenerator()
        
        # Inicializar verificador LLM si está habilitado
        self.verifier = None
        if use_llm:
            try:
                self.verifier = OllamaVerifier(model=llm_model)
                print("✅ Verificador LLM inicializado correctamente")
            except:
                print("⚠️  No se pudo inicializar Ollama. Usando verificación basada en reglas.")
                print(OllamaInstaller.get_installation_instructions())
                self.use_llm = False
    
    def analyze_complete(self, 
                        output_dir: str = "./output",
                        sample_size: int = 5,
                        max_llm_verifications: int = 10) -> Dict:
        """
        Ejecuta el análisis completo del esquema
        
        Args:
            output_dir: Directorio para guardar resultados
            sample_size: Número de filas de muestra por tabla
            max_llm_verifications: Máximo de verificaciones con LLM
        
        Returns:
            Dict con todos los resultados del análisis
        """
        print("\n🚀 INICIANDO ANÁLISIS COMPLETO DEL ESQUEMA")
        print("="*60)
        
        # Crear directorio de salida
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        results = {
            'timestamp': timestamp,
            'database_type': self.db_type,
            'stages': {}
        }
        
        # FASE 1: Extracción del esquema
        print("\n📊 FASE 1: Extrayendo esquema de la base de datos...")
        schema = self.extractor.extract_schema()
        self.extractor.print_schema_summary()
        
        # Guardar esquema
        schema_file = os.path.join(output_dir, f"schema_{timestamp}.json")
        self.extractor.export_schema(schema_file)
        
        results['stages']['extraction'] = {
            'status': 'completed',
            'tables_found': len(schema),
            'schema_file': schema_file
        }
        
        # Obtener datos de muestra
        print("\n📋 Obteniendo datos de muestra...")
        sample_data = {}
        for table_name in list(schema.keys())[:10]:  # Limitar a 10 tablas
            try:
                sample_data[table_name] = self.extractor.get_sample_data(
                    table_name, limit=sample_size
                )
            except:
                print(f"  ⚠️  No se pudieron obtener datos de muestra para {table_name}")
        
        # FASE 2: Detección de relaciones
        print("\n🔍 FASE 2: Detectando relaciones potenciales...")
        
        # Obtener FKs existentes
        existing_fks = {}
        for table_name, table in schema.items():
            for col, ref in table.foreign_keys.items():
                existing_fks[f"{table_name}.{col}"] = ref
        
        # Detectar nuevas relaciones
        candidates = self.detector.detect_relationships(schema, existing_fks)
        print(f"  ✓ Se detectaron {len(candidates)} relaciones potenciales")
        
        # Generar reporte de detección
        detection_report = self.detector.generate_relationship_report(candidates)
        print(detection_report)
        
        # Guardar reporte
        report_file = os.path.join(output_dir, f"detection_report_{timestamp}.txt")
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(detection_report)
        
        results['stages']['detection'] = {
            'status': 'completed',
            'relationships_found': len(candidates),
            'report_file': report_file
        }
        
        # FASE 3: Verificación con LLM
        if self.use_llm and self.verifier and candidates:
            print(f"\n🤖 FASE 3: Verificando relaciones con LLM (máx {max_llm_verifications})...")
            
            # Preparar información del esquema para el verificador
            schema_info = {}
            for table_name, table in schema.items():
                schema_info[table_name] = {
                    'columns': [
                        {
                            'name': col.name,
                            'type': col.data_type,
                            'nullable': col.is_nullable,
                            'primary_key': col.is_primary_key
                        }
                        for col in table.columns
                    ]
                }
            
            # Verificar con LLM
            verified = self.verifier.verify_batch(
                candidates, 
                schema_info, 
                sample_data,
                max_llm_verifications
            )
            
            # Generar reporte de verificación
            verification_report = self.verifier.generate_verification_report(verified)
            print(verification_report)
            
            # Guardar reporte
            verify_file = os.path.join(output_dir, f"verification_report_{timestamp}.txt")
            with open(verify_file, 'w', encoding='utf-8') as f:
                f.write(verification_report)
            
            results['stages']['verification'] = {
                'status': 'completed',
                'relationships_verified': len(verified),
                'valid_relationships': len([v for v in verified if v.is_valid]),
                'report_file': verify_file
            }
        else:
            print("\n⏭️  FASE 3: Saltando verificación con LLM...")
            # Usar verificación basada en reglas
            verified = verify_without_llm(candidates)
            results['stages']['verification'] = {
                'status': 'skipped',
                'reason': 'LLM not available'
            }
        
        # FASE 4: Generación de DBML
        print("\n📐 FASE 4: Generando código DBML...")
        
        # Combinar relaciones existentes y nuevas verificadas
        all_relationships = []
        
        # Agregar relaciones existentes
        for table_name, table in schema.items():
            for source_col, target_ref in table.foreign_keys.items():
                target_parts = target_ref.split('.')
                if len(target_parts) == 2:
                    # Crear objeto VerifiedRelationship para relaciones existentes
                    from dataclasses import dataclass
                    @dataclass
                    class ExistingRel:
                        source_table: str = table_name
                        source_column: str = source_col
                        target_table: str = target_parts[0]
                        target_column: str = target_parts[1]
                        confidence: float = 1.0
                        llm_confidence: float = 1.0
                        relationship_type: str = "foreign_key"
                        cardinality: str = "N:1"
                        explanation: str = "Relación existente en el esquema"
                        is_valid: bool = True
                    
                    all_relationships.append(ExistingRel())
        
        # Agregar nuevas relaciones verificadas
        if 'verified' in locals():
            all_relationships.extend(verified)
        
        # Generar DBML
        dbml_code = self.generator.generate_dbml(
            schema,
            all_relationships,
            project_name=f"Schema Analysis {timestamp}",
            include_indexes=True,
            include_notes=True
        )
        
        # Guardar DBML
        dbml_file = os.path.join(output_dir, f"schema_{timestamp}.dbml")
        self.generator.save_to_file(dbml_code, dbml_file)
        
        # Mejorar DBML con grupos automáticos
        groups = self._auto_generate_table_groups(schema)
        if groups:
            enhanced_dbml = DBMLEnhancer.add_table_groups(dbml_code, groups)
            enhanced_file = os.path.join(output_dir, f"schema_enhanced_{timestamp}.dbml")
            with open(enhanced_file, 'w', encoding='utf-8') as f:
                f.write(enhanced_dbml)
            print(f"  ✓ DBML mejorado guardado en: {enhanced_file}")
        
        results['stages']['generation'] = {
            'status': 'completed',
            'dbml_file': dbml_file,
            'relationships_included': len(all_relationships)
        }
        
        # FASE 5: Resumen final
        print("\n📊 RESUMEN FINAL")
        print("="*60)
        self._print_summary(schema, all_relationships, results)
        
        # Guardar resumen completo
        summary_file = os.path.join(output_dir, f"analysis_summary_{timestamp}.json")
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n✅ Análisis completado. Resultados guardados en: {output_dir}")
        print(f"\n🎨 Para visualizar el diagrama:")
        print(f"   1. Abre el archivo: {dbml_file}")
        print(f"   2. Copia todo el contenido")
        print(f"   3. Ve a: https://dbdiagram.io/d")
        print(f"   4. Pega el código y disfruta tu diagrama ER")
        
        return results
    
    def _auto_generate_table_groups(self, schema: Dict[str, 'Table']) -> Dict[str, List[str]]:
        """Genera grupos de tablas automáticamente basándose en prefijos/patrones"""
        groups = {}
        
        # Agrupar por prefijos comunes
        prefix_groups = {}
        for table_name in schema.keys():
            # Buscar prefijo (ej: user_profile -> user)
            parts = table_name.split('_')
            if len(parts) > 1:
                prefix = parts[0]
                if prefix not in prefix_groups:
                    prefix_groups[prefix] = []
                prefix_groups[prefix].append(table_name)
        
        # Solo crear grupos con más de una tabla
        for prefix, tables in prefix_groups.items():
            if len(tables) > 1:
                groups[f"{prefix}_tables"] = tables
        
        # Agrupar tablas de unión (junction tables)
        junction_tables = []
        for table_name, table in schema.items():
            # Heurística: tablas con solo FKs probablemente son de unión
            fk_count = sum(1 for col in table.columns if col.is_foreign_key)
            total_cols = len(table.columns)
            
            if fk_count >= 2 and fk_count / total_cols > 0.5:
                junction_tables.append(table_name)
        
        if junction_tables:
            groups['junction_tables'] = junction_tables
        
        return groups
    
    def _print_summary(self, schema: Dict[str, 'Table'], 
                      relationships: List, results: Dict):
        """Imprime un resumen del análisis"""
        total_tables = len(schema)
        total_columns = sum(len(table.columns) for table in schema.values())
        total_rows = sum(table.row_count for table in schema.values())
        
        existing_fks = sum(len(table.foreign_keys) for table in schema.values())
        new_relationships = len([r for r in relationships if hasattr(r, 'is_valid') and r.is_valid])
        
        print(f"📊 Tablas analizadas: {total_tables}")
        print(f"📋 Total de columnas: {total_columns}")
        print(f"📈 Total de filas: {total_rows:,}")
        print(f"🔗 Relaciones existentes: {existing_fks}")
        print(f"✨ Nuevas relaciones detectadas: {new_relationships}")
        print(f"📐 Total de relaciones en DBML: {len(relationships)}")

# Script principal de ejemplo
def main():
    """Función principal de ejemplo"""
    print("🔧 SCHEMA ANALYZER - Herramienta de Análisis de Esquemas")
    print("="*60)
    
    # Configuración de ejemplo
    # Para SQLite
    analyzer = SchemaAnalyzer(
        db_type="sqlite",
        connection_params={"database": "example.db"},
        use_llm=True,  # Cambiar a False si no tienes Ollama
        llm_model="llama2"
    )
    
    # Para PostgreSQL
    # analyzer = SchemaAnalyzer(
    #     db_type="postgresql",
    #     connection_params={
    #         "host": "localhost",
    #         "database": "mydb",
    #         "user": "user",
    #         "password": "password"
    #     },
    #     use_llm=True
    # )
    
    # Ejecutar análisis completo
    results = analyzer.analyze_complete(
        output_dir="./schema_analysis_output",
        sample_size=5,
        max_llm_verifications=10
    )
    
    print("\n✅ ¡Análisis completado exitosamente!")

if __name__ == "__main__":
    # Verificar dependencias
    try:
        import pandas
        import numpy
        import sentence_transformers
        print("✅ Todas las dependencias están instaladas")
    except ImportError as e:
        print(f"❌ Falta instalar dependencias: {e}")
        print("Ejecuta: pip install pandas numpy scikit-learn sentence-transformers psycopg2-binary")
        exit(1)
    
    # Ejecutar análisis
    main()