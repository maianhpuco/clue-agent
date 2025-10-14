Here’s a polished, ready-to-paste version of your overview. I fixed grammar, tightened phrasing, and normalized headings and numbering (Stages 1→4).

---

# Overview

Build an **MCP agent — ZERO TRAINING** for a **WSI-agentic system** that reads a whole-slide image (WSI), produces a slide-level diagnosis, and—crucially—**explains the decision with visual and morphological evidence**.

# Objective

* Ingest a short dataset description (e.g., **CAMELYON16**).
* Use prior pathology knowledge (concepts/patterns) to:

  1. **Glance** at low magnification to locate suspicious/abnormal regions.
  2. **Zoom** into candidate regions, **name** the patterns, then produce:

     * a **classification result**, and
     * an **explanatory diagnosis report** (with concept/evidence links).

# Dataset Prior (example: CAMELYON16)

* **Tumor (Metastasis / Positive):** Slides containing any metastatic breast carcinoma in lymph-node tissue. Includes macro-metastases, micro-metastases, and isolated tumor cells (ITCs). Pixel-level tumor regions are annotated in the training set.
* **Normal (Negative):** Slides with no evidence of metastatic tumor in the lymph-node tissue (benign/normal only). No tumor annotations because no metastasis is present.

This dataset prior seeds concept discovery and ontology building.

# Agent Behavior

* Read the dataset description.
* Use a **ReAct-style MCP tool** to search trusted sources and **expand a flat concept list** into a structured **ontology** of morphological patterns relevant to the dataset.
* Ensure concepts include **definitions, synonyms, and relations**, and are suitable for **patch-level reasoning**.

# Stage 1 — Concept & Ontology Construction (Prior Knowledge)

**Goal:** Convert a flat list of concepts (with definitions/synonyms) into a **DAG ontology** with the following relations (no cycles; no duplicate synonyms):

* `is-a`: the concept’s type/category
* `parents`: higher-level nodes
* `exclusive_with`: patterns that should not co-exist at patch scale
* `co_occurs_with`: patterns that often appear together or as neighbors

**Output:** YAML following this schema:

```yaml
concepts:
  - id: <string>                # unique concept id (machine-friendly)
    name: <string>              # human-readable concept name
    definition: <string>        # clear, concise definition
    synonyms: [<string>, ...]   # no duplicates
    is-a: <string>              # concept type/category (e.g., "morphology", "artifact")
    parents: [<string>, ...]    # ids of parent concepts (DAG: no cycles)
    exclusive_with: [<string>, ...]  # mutually exclusive at patch scale
    co_occurs_with: [<string>, ...]  # frequently neighboring/linked concepts
    examples:
      text: [<string>, ...]     # short textual cues, if any
      image_refs: [<uri>, ...]  # optional references for curation
metadata:
  version: 1
  dataset: "CAMELYON16"
  notes: "No cycles; synonyms deduped; ids stable."
```

# Stage 2 — Visual Prior Knowledge (Few-Shot Patch Bank)

**Objective:** Build an ontology-anchored patch bank (few-shot exemplars) using both external images and in-dataset patches, so the agent can reference concrete visual evidence during reasoning and later zooming.

**Actions:**

* **Curate external visuals:** For each concept (and its synonyms), use an image search tool to collect representative example images. Attach these as provisional visual references to ontology nodes.
* **Mine dataset exemplars:** For each concept (and its synonyms), retrieve the top-k candidate patches from the dataset.
* **Score & filter candidates:**

  * **Ontology match:** Score each patch by how well it aligns with the concept’s definition and relations (e.g., `exclusive_with`, `co_occurs_with`).
  * **LLM cross-checking:** Use an LLM to compare each candidate patch against the concept’s visual references (including external examples) and textual definitions. Retain only patches that pass both ontology constraints and LLM consistency checks.
* **Defer fine zooming:** Keep accepted patches as few-shot exemplars; detailed zoom/verification occurs in later stages.

**Output:** An ontology tree enriched with vetted example patches per concept (plus optional external image references). This serves as a **few-shot explanation bank**.

**Storage:** Persist the enriched ontology and exemplars in a **RAG index** (concept metadata + patch embeddings/URIs) for efficient retrieval during inference.

# Stage 3 — Saliency & Concept Scoring (CONCH)

**Inputs:**

* Pretrained **CONCH** encoder for text–image similarity.
* Patch features extracted from the WSI at one or more magnifications.
* Text embeddings for each ontology concept (e.g., names + definitions + synonyms).

**Procedure:**

1. **Patch embeddings:** Extract features for all patches across the slide.
2. **Text embeddings:** Compute embeddings for each concept using the CONCH text tower.
3. **Similarity:** Compute similarity between each patch feature and each concept embedding.
4. **Aggregation:** For each concept, aggregate per-patch similarities to compute:

   * **Patch-level scores** (for heatmaps/attention maps).
   * **Region/slide-level scores** (e.g., mean, top-k mean, or attention-weighted).
5. **Outputs:**

   * **Concept heatmaps** (per concept).
   * **Region proposals** (top-k concept-evidence regions).
   * **Preliminary slide-level concept profile** (vector of concept scores).

# Stage 4 — Pattern Matching & Inference

Use the ontology + few-shot patch bank as **prior knowledge (RAG)** to query each slide:

* Retrieve relevant concepts and exemplars.
* Match patterns against candidate regions (guided by concept heatmaps and region proposals).
* Produce slide-level predictions with supporting evidence.

# Reporting

* Produce a **classification result** (e.g., Tumor vs Normal).
* Generate an **explanation** that:

  * cites **top concept evidence** (concept names + supporting regions),
  * references **where** (coordinates/tiles) and **why** (definition-aligned cues),
  * resolves contradictions via `exclusive_with`,
  * highlights supporting context via `co_occurs_with`.

# Notes

* Maintain **DAG integrity** (no cycles).
* Keep **concept ids** stable for downstream indexing.
* Prefer **top-k** or **attention-weighted** aggregation to avoid dilution across many patches.
* Ensure explanations map directly to **visible evidence** (heatmaps/tiles).
