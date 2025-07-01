"""
Fase 4: Generador de DBML (Database Markup Language)
Genera código DBML para crear diagramas ER con dbdiagram.io
"""

from typing import Dict, List, Optional, Set
from dataclasses import dataclass
import re
import pandas as pd

class DBMLGenerator:
    def __init__(self):
        """Inicializa el generador de DBML"""
        self.dbml_content = []
        self.type_mapping = {
            # PostgreSQL to DBML
            'integer': 'int',
            'bigint': 'bigint',
            'smallint': 'int',
            'decimal': 'decimal',
            'numeric': 'decimal',
            'real': 'float',
            'double precision': 'float',
            'character varying': 'varchar',
            'varchar': 'varchar',
            'character': 'char',
            'char': 'char',
            'text': 'text',
            'boolean': 'boolean',
            'bool': 'boolean',
            'date': 'date',
            'timestamp': 'timestamp',
            'timestamp without time zone': 'timestamp',
            'timestamp with time zone': 'timestamptz',
            'time': 'time',
            'json': 'json',
            'jsonb': 'jsonb',
            'uuid': 'uuid',
            
            # SQLite to DBML
            'INTEGER': 'int',
            'REAL': 'float',
            'TEXT': 'text',
            'BLOB': 'blob',
            'NUMERIC': 'decimal',
            
            # MySQL to DBML
            'tinyint': 'int',
            'mediumint': 'int',
            'float': 'float',
            'double': 'float',
            'datetime': 'datetime',
            'tinytext': 'text',
            'mediumtext': 'text',
            'longtext': 'text'
        }
    
    def generate_dbml(self,
                     schema: Dict[str, 'Table'],
                     relationships: List['VerifiedRelationship'],
                     project_name: str = "Database Schema",
                     include_indexes: bool = True,
                     include_notes: bool = True) -> str:
        """
        Genera código DBML completo
        
        Args:
            schema: Diccionario de tablas del esquema
            relationships: Lista de relaciones verificadas
            project_name: Nombre del proyecto
            include_indexes: Si incluir definiciones de índices
            include_notes: Si incluir notas y comentarios
        
        Returns:
            Código DBML como string
        """
        self.dbml_content = []
        
        # Header del proyecto
        self._add_project_header(project_name)
        
        # Generar tablas
        for table_name, table in schema.items():
            self._add_table(table_name, table, include_indexes, include_notes)
        
        # Generar relaciones
        self._add_relationships(relationships)
        
        # Agregar notas finales si están habilitadas
        if include_notes:
            self._add_footer_notes(schema, relationships)
        
        return '\n'.join(self.dbml_content)
    
    def _add_project_header(self, project_name: str):
        """Agrega el header del proyecto"""
        self.dbml_content.extend([
            f"// {project_name}",
            f"// Generated with Python Schema Analyzer",
            f"// https://dbdiagram.io/d",
            "",
            f"Project {self._sanitize_name(project_name)} " + "{",
            "  database_type: 'PostgreSQL'",
            "  Note: 'Esquema de base de datos generado automáticamente'",
            "}",
            ""
        ])
    
    def _add_table(self, table_name: str, table: 'Table', 
                   include_indexes: bool, include_notes: bool):
        """Agrega una tabla al DBML"""
        # Inicio de tabla
        self.dbml_content.append(f"Table {self._sanitize_name(table_name)} " + "{")
        
        # Agregar columnas
        for col in table.columns:
            self._add_column(col, table_name)
        
        # Agregar índices si está habilitado
        if include_indexes and (table.primary_keys or any(col.unique for col in table.columns)):
            self.dbml_content.append("")
            self.dbml_content.append("  Indexes {")
            
            # Primary key index
            if table.primary_keys:
                pk_cols = ', '.join(table.primary_keys)
                self.dbml_content.append(f"    ({pk_cols}) [pk]")
            
            # Unique indexes
            for col in table.columns:
                if col.unique and not col.is_primary_key:
                    self.dbml_content.append(f"    {col.name} [unique]")
            
            self.dbml_content.append("  }")
        
        # Agregar nota de tabla si está habilitado
        if include_notes and table.row_count > 0:
            self.dbml_content.append("")
            self.dbml_content.append(f"  Note: '{table.row_count:,} filas'")
        
        self.dbml_content.append("}")
        self.dbml_content.append("")
    
    def _add_column(self, column: 'Column', table_name: str):
        """Agrega una columna al DBML"""
        # Nombre y tipo
        col_type = self._map_type(column.data_type)
        line = f"  {self._sanitize_name(column.name)} {col_type}"
        
        # Agregar constraints
        constraints = []
        
        if column.is_primary_key:
            constraints.append("pk")
        
        if not column.is_nullable and not column.is_primary_key:
            constraints.append("not null")
        
        if column.unique and not column.is_primary_key:
            constraints.append("unique")
        
        if column.default_value:
            # Sanitizar el valor default
            default_val = str(column.default_value).replace("'", "\\'")
            constraints.append(f"default: '{default_val}'")
        
        # Agregar nota si es FK (será referenciada en las relaciones)
        if column.is_foreign_key:
            constraints.append(f"note: 'FK a {column.foreign_key_ref}'")
        
        # Agregar constraints a la línea
        if constraints:
            line += f" [{', '.join(constraints)}]"
        
        self.dbml_content.append(line)
    
    def _add_relationships(self, relationships: List['VerifiedRelationship']):
        """Agrega las relaciones al DBML"""
        if not relationships:
            return
        
        self.dbml_content.extend([
            "// Relaciones",
            ""
        ])
        
        # Agrupar por tipo de cardinalidad
        grouped = {}
        for rel in relationships:
            if rel.is_valid:  # Solo incluir relaciones válidas
                card = rel.cardinality
                if card not in grouped:
                    grouped[card] = []
                grouped[card].append(rel)
        
        # Generar referencias por grupo
        for cardinality, rels in grouped.items():
            if rels:
                self.dbml_content.append(f"// {cardinality} relationships")
                
                for rel in rels:
                    ref_symbol = self._get_reference_symbol(cardinality)
                    
                    # Formato: Ref: table1.column1 > table2.column2
                    ref_line = (f"Ref: {self._sanitize_name(rel.source_table)}."
                              f"{self._sanitize_name(rel.source_column)} "
                              f"{ref_symbol} "
                              f"{self._sanitize_name(rel.target_table)}."
                              f"{self._sanitize_name(rel.target_column)}")
                    
                    # Agregar nota con la explicación si existe
                    if rel.explanation:
                        # Truncar explicación larga
                        short_explanation = rel.explanation[:50] + "..." if len(rel.explanation) > 50 else rel.explanation
                        ref_line += f" // {short_explanation}"
                    
                    self.dbml_content.append(ref_line)
                
                self.dbml_content.append("")
    
    def _get_reference_symbol(self, cardinality: str) -> str:
        """Obtiene el símbolo de referencia según la cardinalidad"""
        symbols = {
            "1:1": "-",
            "1:N": "<",
            "N:1": ">",
            "N:M": "<>",
            "one-to-one": "-",
            "one-to-many": "<",
            "many-to-one": ">",
            "many-to-many": "<>"
        }
        return symbols.get(cardinality, ">")
    
    def _map_type(self, original_type: str) -> str:
        """Mapea tipos de datos SQL a tipos DBML"""
        # Limpiar el tipo (remover tamaños, etc.)
        clean_type = original_type.lower().split('(')[0].strip()
        
        # Buscar en el mapeo
        return self.type_mapping.get(clean_type, 'varchar')
    
    def _sanitize_name(self, name: str) -> str:
        """Sanitiza nombres para DBML"""
        # Si contiene espacios o caracteres especiales, usar comillas
        if re.search(r'[^a-zA-Z0-9_]', name):
            return f'"{name}"'
        return name
    
    def _add_footer_notes(self, schema: Dict[str, 'Table'], 
                         relationships: List['VerifiedRelationship']):
        """Agrega notas finales con estadísticas"""
        total_tables = len(schema)
        total_columns = sum(len(table.columns) for table in schema.values())
        total_relationships = len([r for r in relationships if r.is_valid])
        
        self.dbml_content.extend([
            "",
            "// Estadísticas del esquema",
            f"// Total de tablas: {total_tables}",
            f"// Total de columnas: {total_columns}",
            f"// Total de relaciones: {total_relationships}",
            "",
            "// Para visualizar este diagrama:",
            "// 1. Copia todo este código",
            "// 2. Ve a https://dbdiagram.io/d",
            "// 3. Pega el código en el editor",
            "// 4. ¡Disfruta tu diagrama ER!"
        ])
    
    def save_to_file(self, dbml_code: str, filename: str = "schema.dbml"):
        """Guarda el código DBML en un archivo"""
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(dbml_code)
        print(f"✅ DBML guardado en: {filename}")
    
    def generate_visualization_url(self, dbml_code: str) -> str:
        """
        Genera URL para visualización directa (si dbdiagram.io lo soportara)
        Nota: Actualmente dbdiagram.io no soporta URLs directas con código
        """
        # Por ahora, solo retornar la URL base
        return "https://dbdiagram.io/d"

# Utilidades adicionales para DBML
class DBMLEnhancer:
    """Clase para mejorar y enriquecer el DBML generado"""
    
    @staticmethod
    def add_table_groups(dbml_code: str, groups: Dict[str, List[str]]) -> str:
        """
        Agrega grupos de tablas al DBML
        
        Args:
            dbml_code: Código DBML original
            groups: Dict con nombre_grupo -> lista_de_tablas
        
        Returns:
            DBML mejorado con grupos
        """
        lines = dbml_code.split('\n')
        insert_index = 0
        
        # Buscar dónde insertar los grupos (después del Project)
        for i, line in enumerate(lines):
            if line.strip() == '}' and 'Project' in lines[max(0, i-5):i]:
                insert_index = i + 1
                break
        
        # Crear definiciones de grupos
        group_lines = ["\n// Grupos de tablas"]
        for group_name, tables in groups.items():
            group_lines.append(f"\nTableGroup {group_name} " + "{")
            for table in tables:
                group_lines.append(f"  {table}")
            group_lines.append("}")
        
        # Insertar grupos
        lines[insert_index:insert_index] = group_lines
        
        return '\n'.join(lines)
    
    @staticmethod
    def add_colors(dbml_code: str, color_scheme: Dict[str, str]) -> str:
        """
        Agrega colores a las tablas
        
        Args:
            dbml_code: Código DBML original
            color_scheme: Dict con tabla -> color (hex)
        
        Returns:
            DBML con colores
        """
        lines = dbml_code.split('\n')
        result = []
        
        for line in lines:
            result.append(line)
            
            # Si es una definición de tabla, agregar color
            if line.strip().startswith('Table '):
                table_match = re.search(r'Table\s+([^\s{]+)', line)
                if table_match:
                    table_name = table_match.group(1).strip('"')
                    if table_name in color_scheme:
                        # Insertar color como primera línea de la tabla
                        result.append(f"  color: {color_scheme[table_name]}")
        
        return '\n'.join(result)
    
    @staticmethod
    def generate_sample_data_notes(schema: Dict[str, 'Table'], 
                                 sample_data: Dict[str, pd.DataFrame]) -> Dict[str, str]:
        """
        Genera notas con datos de ejemplo para cada tabla
        
        Returns:
            Dict con tabla -> nota_con_ejemplos
        """
        notes = {}
        
        for table_name, df in sample_data.items():
            if not df.empty:
                # Tomar primera fila como ejemplo
                example = df.iloc[0].to_dict()
                note_parts = []
                
                for col, val in list(example.items())[:3]:  # Max 3 campos
                    note_parts.append(f"{col}: {str(val)[:20]}")
                
                notes[table_name] = f"Ejemplo: {', '.join(note_parts)}"
        
        return notes