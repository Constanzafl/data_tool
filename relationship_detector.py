"""
Fase 2: Detector de Relaciones con Embeddings
Detecta relaciones potenciales entre tablas usando similitud semántica
"""

import numpy as np
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import re
from collections import defaultdict

@dataclass
class RelationshipCandidate:
    source_table: str
    source_column: str
    target_table: str
    target_column: str
    confidence: float
    relationship_type: str  # "one-to-many", "many-to-one", "one-to-one"
    evidence: List[str]  # Razones por las que se detectó la relación

class RelationshipDetector:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Inicializa el detector con un modelo de embeddings
        """
        self.model = SentenceTransformer(model_name)
        self.common_pk_patterns = [
            r'^id$', r'_id$', r'^pk_', r'_pk$', r'^guid$', r'_guid$',
            r'^uuid$', r'_uuid$', r'^code$', r'_code$', r'^key$', r'_key$'
        ]
        self.common_fk_patterns = [
            r'_id$', r'_fk$', r'_ref$', r'_code$', r'_key$',
            r'^fk_', r'^ref_', r'^parent_', r'^child_'
        ]
        
    def detect_relationships(self, schema: Dict[str, 'Table'], 
                           existing_fks: Optional[Dict] = None) -> List[RelationshipCandidate]:
        """
        Detecta relaciones potenciales entre tablas
        
        Args:
            schema: Diccionario de tablas del esquema
            existing_fks: FKs ya conocidas para excluirlas
        
        Returns:
            Lista de candidatos de relación ordenados por confianza
        """
        candidates = []
        existing_fks = existing_fks or {}
        
        # 1. Detección basada en patrones de nombres
        pattern_candidates = self._detect_by_patterns(schema)
        candidates.extend(pattern_candidates)
        
        # 2. Detección basada en similitud semántica
        semantic_candidates = self._detect_by_semantic_similarity(schema)
        candidates.extend(semantic_candidates)
        
        # 3. Detección basada en análisis de datos
        data_candidates = self._detect_by_data_analysis(schema)
        candidates.extend(data_candidates)
        
        # 4. Consolidar y rankear candidatos
        final_candidates = self._consolidate_candidates(candidates, existing_fks)
        
        return sorted(final_candidates, key=lambda x: x.confidence, reverse=True)
    
    def _detect_by_patterns(self, schema: Dict[str, 'Table']) -> List[RelationshipCandidate]:
        """Detecta relaciones basándose en patrones comunes de nomenclatura"""
        candidates = []
        
        for source_table_name, source_table in schema.items():
            for source_col in source_table.columns:
                # Buscar columnas que parecen FKs
                if self._looks_like_fk(source_col.name):
                    # Intentar encontrar la tabla referenciada
                    potential_targets = self._find_target_table(
                        source_col.name, source_table_name, schema
                    )
                    
                    for target_table_name, target_col_name, confidence in potential_targets:
                        if target_table_name in schema:
                            evidence = [
                                f"Nombre de columna '{source_col.name}' sugiere FK",
                                f"Patrón coincide con tabla '{target_table_name}'"
                            ]
                            
                            candidates.append(RelationshipCandidate(
                                source_table=source_table_name,
                                source_column=source_col.name,
                                target_table=target_table_name,
                                target_column=target_col_name,
                                confidence=confidence,
                                relationship_type="many-to-one",
                                evidence=evidence
                            ))
        
        return candidates
    
    def _detect_by_semantic_similarity(self, schema: Dict[str, 'Table']) -> List[RelationshipCandidate]:
        """Detecta relaciones usando similitud semántica entre nombres"""
        candidates = []
        
        # Preparar textos para embeddings
        column_texts = []
        column_info = []  # (table, column, description)
        
        for table_name, table in schema.items():
            for col in table.columns:
                # Crear descripción rica del contexto
                text = f"{table_name} {col.name} {col.data_type}"
                
                # Agregar contexto adicional
                if col.is_primary_key:
                    text += " primary key identifier"
                
                column_texts.append(text)
                column_info.append((table_name, col.name, col))
        
        # Generar embeddings
        embeddings = self.model.encode(column_texts)
        
        # Calcular similitudes
        similarities = cosine_similarity(embeddings)
        
        # Encontrar pares similares
        threshold = 0.7
        for i in range(len(column_info)):
            for j in range(i + 1, len(column_info)):
                sim = similarities[i][j]
                
                if sim > threshold:
                    table1, col1, colobj1 = column_info[i]
                    table2, col2, colobj2 = column_info[j]
                    
                    # No sugerir relaciones dentro de la misma tabla
                    if table1 == table2:
                        continue
                    
                    # Determinar dirección de la relación
                    if colobj1.is_primary_key and not colobj2.is_primary_key:
                        # col1 es PK, col2 podría ser FK
                        candidates.append(RelationshipCandidate(
                            source_table=table2,
                            source_column=col2,
                            target_table=table1,
                            target_column=col1,
                            confidence=sim * 0.8,  # Ajustar confianza
                            relationship_type="many-to-one",
                            evidence=[
                                f"Alta similitud semántica ({sim:.2f})",
                                f"'{col1}' es PK en '{table1}'"
                            ]
                        ))
                    elif colobj2.is_primary_key and not colobj1.is_primary_key:
                        # col2 es PK, col1 podría ser FK
                        candidates.append(RelationshipCandidate(
                            source_table=table1,
                            source_column=col1,
                            target_table=table2,
                            target_column=col2,
                            confidence=sim * 0.8,
                            relationship_type="many-to-one",
                            evidence=[
                                f"Alta similitud semántica ({sim:.2f})",
                                f"'{col2}' es PK en '{table2}'"
                            ]
                        ))
        
        return candidates
    
    def _detect_by_data_analysis(self, schema: Dict[str, 'Table']) -> List[RelationshipCandidate]:
        """Detecta relaciones analizando los datos (cardinalidad, valores únicos, etc.)"""
        candidates = []
        
        # Por ahora, análisis básico basado en nombres y tipos
        # En una implementación completa, aquí analizaríamos:
        # - Cardinalidad de las relaciones
        # - Overlap de valores entre columnas
        # - Distribución de datos
        
        for source_table_name, source_table in schema.items():
            for source_col in source_table.columns:
                # Buscar columnas con tipos compatibles para IDs
                if source_col.data_type.lower() in ['integer', 'bigint', 'int', 'bigserial']:
                    for target_table_name, target_table in schema.items():
                        if source_table_name == target_table_name:
                            continue
                        
                        for target_col in target_table.columns:
                            if (target_col.is_primary_key and 
                                target_col.data_type.lower() in ['integer', 'bigint', 'int', 'bigserial']):
                                
                                # Verificar si el nombre sugiere relación
                                if self._names_suggest_relationship(
                                    source_col.name, target_col.name, 
                                    source_table_name, target_table_name
                                ):
                                    candidates.append(RelationshipCandidate(
                                        source_table=source_table_name,
                                        source_column=source_col.name,
                                        target_table=target_table_name,
                                        target_column=target_col.name,
                                        confidence=0.6,
                                        relationship_type="many-to-one",
                                        evidence=[
                                            "Tipos de datos compatibles",
                                            "Nombres sugieren relación"
                                        ]
                                    ))
        
        return candidates
    
    def _looks_like_fk(self, column_name: str) -> bool:
        """Determina si un nombre de columna parece una FK"""
        col_lower = column_name.lower()
        
        # Verificar patrones comunes de FK
        for pattern in self.common_fk_patterns:
            if re.search(pattern, col_lower):
                return True
        
        # Verificar nombres compuestos (ej: customer_id, order_code)
        if '_' in col_lower and any(part in ['id', 'code', 'key', 'ref'] 
                                   for part in col_lower.split('_')):
            return True
        
        return False
    
    def _find_target_table(self, fk_column: str, source_table: str, 
                          schema: Dict) -> List[Tuple[str, str, float]]:
        """Encuentra posibles tablas objetivo para una FK"""
        targets = []
        fk_lower = fk_column.lower()
        
        # Estrategia 1: Nombre exacto (ej: customer_id -> customer.id)
        if '_id' in fk_lower:
            potential_table = fk_lower.replace('_id', '')
            if potential_table in schema:
                targets.append((potential_table, 'id', 0.9))
            
            # Plural a singular (ej: customers_id -> customer.id)
            if potential_table.endswith('s'):
                singular = potential_table[:-1]
                if singular in schema:
                    targets.append((singular, 'id', 0.85))
        
        # Estrategia 2: Buscar tabla con nombre similar
        for table_name in schema:
            if table_name != source_table:
                similarity = self._string_similarity(fk_lower, table_name.lower())
                if similarity > 0.6:
                    # Buscar PK en la tabla objetivo
                    target_table = schema[table_name]
                    for pk in target_table.primary_keys:
                        targets.append((table_name, pk, similarity))
        
        return targets
    
    def _names_suggest_relationship(self, source_col: str, target_col: str,
                                   source_table: str, target_table: str) -> bool:
        """Verifica si los nombres sugieren una relación"""
        source_lower = source_col.lower()
        target_table_lower = target_table.lower()
        
        # Ej: customer_id relacionado con tabla customer
        if target_table_lower in source_lower:
            return True
        
        # Ej: Plural/singular
        if target_table_lower + 's' in source_lower:
            return True
        if target_table_lower.endswith('s') and target_table_lower[:-1] in source_lower:
            return True
        
        return False
    
    def _string_similarity(self, s1: str, s2: str) -> float:
        """Calcula similitud simple entre strings"""
        # Implementación básica - en producción usar Levenshtein o similar
        s1_parts = set(s1.split('_'))
        s2_parts = set(s2.split('_'))
        
        if not s1_parts or not s2_parts:
            return 0.0
        
        intersection = len(s1_parts & s2_parts)
        union = len(s1_parts | s2_parts)
        
        return intersection / union if union > 0 else 0.0
    
    def _consolidate_candidates(self, candidates: List[RelationshipCandidate],
                               existing_fks: Dict) -> List[RelationshipCandidate]:
        """Consolida candidatos duplicados y filtra los ya existentes"""
        consolidated = {}
        
        for candidate in candidates:
            # Crear clave única
            key = (
                candidate.source_table,
                candidate.source_column,
                candidate.target_table,
                candidate.target_column
            )
            
            # Verificar si ya existe como FK
            existing_key = f"{candidate.source_table}.{candidate.source_column}"
            if existing_key in existing_fks:
                continue
            
            # Consolidar evidencia y confianza
            if key in consolidated:
                existing = consolidated[key]
                # Combinar evidencia
                existing.evidence.extend(candidate.evidence)
                existing.evidence = list(set(existing.evidence))
                # Actualizar confianza (máximo)
                existing.confidence = max(existing.confidence, candidate.confidence)
            else:
                consolidated[key] = candidate
        
        return list(consolidated.values())
    
    def generate_relationship_report(self, candidates: List[RelationshipCandidate]) -> str:
        """Genera un reporte de las relaciones detectadas"""
        report = []
        report.append("="*80)
        report.append("REPORTE DE RELACIONES DETECTADAS")
        report.append("="*80)
        
        # Agrupar por nivel de confianza
        high_confidence = [c for c in candidates if c.confidence >= 0.8]
        medium_confidence = [c for c in candidates if 0.6 <= c.confidence < 0.8]
        low_confidence = [c for c in candidates if c.confidence < 0.6]
        
        if high_confidence:
            report.append("\n🟢 ALTA CONFIANZA (>= 80%)")
            report.append("-" * 40)
            for rel in high_confidence:
                report.append(f"\n{rel.source_table}.{rel.source_column} → "
                            f"{rel.target_table}.{rel.target_column}")
                report.append(f"  Confianza: {rel.confidence:.1%}")
                report.append(f"  Tipo: {rel.relationship_type}")
                report.append("  Evidencia:")
                for evidence in rel.evidence:
                    report.append(f"    - {evidence}")
        
        if medium_confidence:
            report.append("\n🟡 CONFIANZA MEDIA (60-79%)")
            report.append("-" * 40)
            for rel in medium_confidence:
                report.append(f"\n{rel.source_table}.{rel.source_column} → "
                            f"{rel.target_table}.{rel.target_column}")
                report.append(f"  Confianza: {rel.confidence:.1%}")
        
        if low_confidence:
            report.append("\n🔴 BAJA CONFIANZA (< 60%)")
            report.append("-" * 40)
            report.append(f"Se encontraron {len(low_confidence)} relaciones con baja confianza")
        
        report.append(f"\n\nTotal de relaciones detectadas: {len(candidates)}")
        
        return "\n".join(report)