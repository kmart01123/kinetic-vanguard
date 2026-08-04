export type Placement =
  | "title" | "heading" | "body" | "table" | "label" | "option"
  | "button" | "aria-label" | "description" | "status" | "banner"
  | "metadata" | "link" | "noscript" | "facet_count";

export type AuthoritativeText = Readonly<{
  kind: "authoritative";
  text: string;
  sourcePath: string;
  placement: Placement;
}>;

export type UiTextToken = Readonly<{
  kind: "ui";
  text: string;
  tokenId: string;
  placement: Placement;
}>;

export type DerivedOutput = Readonly<{
  kind: "derived";
  text: string;
  derivationId: string;
  placement: Placement;
}>;

export type ComposedText = Readonly<{
  kind: "composed";
  text: string;
  templateId: string;
  placement: Placement;
  constituents: readonly (AuthoritativeText | DerivedOutput | UiTextToken)[];
}>;

export type TextValue = AuthoritativeText | UiTextToken | DerivedOutput | ComposedText;

export interface InlineNode {
  type: "text" | "emphasis" | "strong" | "code" | "term_reference" | "typed_value";
  text?: string;
  label?: string;
  source_unit_id: string;
  value?: { kind: string; value?: string | number; count?: number; sides?: number; modifier?: number; unit?: string };
}

export interface ContentBlock {
  type: "paragraph" | "list" | "note" | "table" | "example" | "tier" | "example_play_section";
  inlines?: InlineNode[];
  style?: "ordered" | "unordered";
  kind?: "note" | "warning";
  items?: InlineNode[][];
  headers?: InlineNode[][];
  rows?: InlineNode[][][];
  title?: InlineNode[];
  heading?: InlineNode[];
  discipline?: "cryokinesis" | "pyrokinesis" | "psychokinesis" | "electrokinesis";
  tier?: number;
  body?: ContentBlock[];
}


export interface Entity {
  id: string;
  title: string;
  short_title?: string;
  publishable: true;
  kind: string;
  level?: number;
  progression_section?: "foundation" | "reference";
  psi_cost?: number;
  activation?: string;
  requires_concentration?: boolean;
  content: ContentBlock[];
  classifications: {
    rules_area: string[];
    entity_kind: string;
    feature_role?: string;
    acquisition_mode?: string;
  };
  presentation_metadata: {
    primary_rules_area: string;
    canonical_topic_by_area: Record<string, string>;
  };
  origins: Array<{ source_unit_ids: string[] }>;
  related_entity_ids?: string[];
}

export interface Topic { id: string; title: string; entity_ids: string[]; order: number }
export interface Category { id: string; label: string; order: number; default_topic_id: string; topics: Topic[] }
export interface VocabularyValue { id: string; label: string; order: number }

export interface Authority {
  schema_version: string;
  rules_version: string;
  metadata: { title: string; attribution: string; license: string; compatibility?: string; release_notes?: string };
  vocabularies: Record<string, VocabularyValue[]>;
  facets: Array<{
    id: string; label: string; cardinality: "single" | "multi"; requiredness: "always" | "applicable";
    applicability: { kind: "all" | "entity_kind" | "rules_area"; values?: string[] };
    order: number; vocabulary: string;
  }>;
  entities: Entity[];
  navigation: { default_category_id: string; categories: Category[] };
  audits?: Array<{id:string; assertion:string; subject_ids:string[]}>;
}

export interface Diagnostic { severity: "error" | "warning"; code: string; message: string; path?: string }

export interface SourceSpan { start: number; end: number }
export interface SourceUnit {
  id: string; type: string; spans: SourceSpan[]; location: { line: number; column: number };
  content_sha256: string; normalized_source: string; inline_metadata: { link_destinations: string[] };
}
