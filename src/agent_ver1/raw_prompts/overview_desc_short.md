Here’s a tight summary of your agent spec:

# Goal

A **zero-training MCP agent** that reads a WSI, outputs a **slide-level diagnosis**, and **explains** it with visual/morphological evidence.

# Inputs

* Short dataset prior (e.g., CAMELYON16 Tumor vs Normal).
* Prior pathology knowledge (concepts/patterns).

# Behavior (Glance → Zoom → Explain)

1. **Glance** at low magnification to find suspicious regions.
2. **Zoom** into candidates, **name** patterns, then report classification + rationale.

# Pipeline (4 Stages)

1. **Concept & Ontology (Prior)**

   * Convert a flat concept list into a **DAG ontology** with `is-a`, `parents`, `exclusive_with`, `co_occurs_with`.
   * Output as YAML (no cycles, deduped synonyms).

2. **Visual Prior (Few-Shot Patch Bank)**

   * Gather **external example images** and **top-k dataset patches** per concept (+ synonyms).
   * **Score & filter** via ontology constraints and **LLM cross-checks**.
   * Store vetted patches as a **few-shot explanation bank** in a **RAG index**.

3. **Saliency & Concept Scoring (CONCH)**

   * Extract **patch embeddings** and **concept text embeddings** (CONCH).
   * Compute patch↔concept **similarities**; aggregate (mean/top-k/attention) to form:

     * **Concept heatmaps**, **region proposals**, and a **slide-level concept profile**.

4. **Pattern Matching & Inference**

   * Use ontology + patch bank (RAG) to retrieve concepts/exemplars.
   * Match patterns in candidate regions and **predict** slide label with evidence.

# Reporting

* Output **classification** (e.g., Tumor/Normal).
* Generate **explanations** citing: concepts, coordinates/tiles, definition-aligned cues, `exclusive_with` contradictions, and `co_occurs_with` context.

# Constraints & Preferences

* Keep **DAG integrity**, **stable concept IDs**.
* Prefer **top-k/attention-weighted** aggregation.
* Explanations must point to **visible evidence** (tiles/heatmaps).
