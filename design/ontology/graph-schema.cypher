// Neo4j graph schema for Methodology Ontology Enforcement
// Run this to initialize the graph schema (indexes + constraints)

// ── Feature node ──────────────────────────────────────────
CREATE CONSTRAINT feature_id_unique IF NOT EXISTS
  FOR (f:Feature) REQUIRE f.feature_id IS UNIQUE;

CREATE INDEX feature_session_idx IF NOT EXISTS
  FOR (f:Feature) ON (f.session_key);

CREATE INDEX feature_status_idx IF NOT EXISTS
  FOR (f:Feature) ON (f.status);

// ── Supporting node indexes ───────────────────────────────
CREATE INDEX acceptance_case_id_idx IF NOT EXISTS
  FOR (a:AcceptanceCase) ON (a.case_id);

CREATE INDEX design_decision_id_idx IF NOT EXISTS
  FOR (d:DesignDecision) ON (d.decision_id);

CREATE INDEX evidence_id_idx IF NOT EXISTS
  FOR (e:Evidence) ON (e.evidence_id);

CREATE INDEX gate_result_id_idx IF NOT EXISTS
  FOR (g:GateResult) ON (g.gate_id);

// ── Node property templates (for reference) ──────────────

// Feature
// (:Feature {
//   feature_id: string,      // UUID
//   title: string,
//   change_type: string,     // ChangeType enum value
//   current_phase: string,   // Phase enum value
//   status: string,          // active | completed | abandoned
//   session_key: string,
//   skip_reasons: string,    // JSON string: {phase: reason}
//   created_at: string,      // ISO datetime
//   updated_at: string       // ISO datetime
// })

// AcceptanceCase
// (:AcceptanceCase {
//   case_id: string,
//   title: string,
//   file_path: string,
//   status: string,          // draft | approved | deprecated
//   created_at: string
// })

// DesignDecision
// (:DesignDecision {
//   decision_id: string,
//   title: string,
//   file_path: string,
//   status: string,          // active | superseded
//   created_at: string
// })

// Evidence
// (:Evidence {
//   evidence_id: string,
//   type: string,            // test_result | trace | file_change
//   summary: string,
//   file_path: string,
//   collected_at: string
// })

// GateResult
// (:GateResult {
//   gate_id: string,
//   gate_check: string,
//   phase_from: string,
//   phase_to: string,
//   passed: boolean,
//   skip_reason: string,
//   checked_at: string
// })

// RegressionCase
// (:RegressionCase {
//   case_id: string,
//   title: string,
//   file_path: string,
//   created_at: string
// })

// ── Relationships ─────────────────────────────────────────

// (Task)-[:IMPLEMENTS_FEATURE]->(Feature)
// (AcceptanceCase)-[:BELONGS_TO]->(Feature)
// (DesignDecision)-[:COVERS]->(Feature)
// (Evidence)-[:EVIDENCES]->(Feature)
// (GateResult)-[:CHECKS]->(Feature)
// (RegressionCase)-[:REGRESSES]->(Feature)
