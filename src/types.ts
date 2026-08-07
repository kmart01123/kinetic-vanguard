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
  value?: { kind: string; value?: string | number; count?: number; sides?: number; modifier?: number; unit?: string };
}

export type ReferenceGroup =
  | "common_features" | "advanced_training" | "cryokinesis"
  | "pyrokinesis" | "psychokinesis" | "electrokinesis";

export type ReferenceLevel =
  | "3rd" | "5th" | "7th" | "10th" | "15th"
  | "18th" | "20th" | "15th+" | "18th+";

export type TableRowReference =
  | { entity_id: string; reference_level: ReferenceLevel }
  | { reference_group: ReferenceGroup; reference_level: ReferenceLevel };

export type ExamplePhaseBlock =
  | { type: "paragraph"; inlines: InlineNode[] }
  | { type: "list"; style: "ordered" | "unordered"; items: InlineNode[][] };

export interface ContentBlock {
  type: "paragraph" | "list" | "note" | "table" | "example" | "tier" | "example_play_section";
  inlines?: InlineNode[];
  style?: "ordered" | "unordered";
  kind?: "note" | "warning";
  items?: InlineNode[][];
  headers?: InlineNode[][];
  rows?: InlineNode[][][];
  row_references?: TableRowReference[];
  title?: InlineNode[];
  heading?: InlineNode[];
  discipline?: "cryokinesis" | "pyrokinesis" | "psychokinesis" | "electrokinesis";
  tier?: number;
  body?: ContentBlock[];
  setup?: ExamplePhaseBlock[];
  activation?: ExamplePhaseBlock[];
  rolls_or_saves?: ExamplePhaseBlock[];
  damage?: ExamplePhaseBlock[];
  effects?: ExamplePhaseBlock[];
  result?: ExamplePhaseBlock[];
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
  concentration_duration?: string;
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
  related_entity_ids?: string[];
}

export type CalculatorSave = "strength" | "constitution" | "dexterity" | "intelligence" | "charisma";
export type CalculatorDamageResolution = "always" | "failed_save" | "half_on_success";

export type CalculatorDamage =
  | { kind: "none"; resolution: CalculatorDamageResolution }
  | { kind: "fixed"; resolution: CalculatorDamageResolution; value: number }
  | { kind: "dice"; resolution: CalculatorDamageResolution; count: number; sides: number }
  | { kind: "manifested_strike_dice"; resolution: CalculatorDamageResolution; count: number }
  | { kind: "psionic_ability_modifier"; resolution: CalculatorDamageResolution; multiplier?: number };

export interface CalculatorTier {
  tier: 0 | 1 | 2;
  damage: CalculatorDamage;
  secondary_damage?: CalculatorDamage;
  save?: CalculatorSave;
}

export type CalculatorDelivery = "on_hit_rider" | "standalone";

export interface CalculatorFeature {
  entity_id: string;
  delivery: CalculatorDelivery;
  tiers: CalculatorTier[];
}

export interface CalculatorLevelBand {
  minimum_level: number;
  maximum_level: number;
  value: number;
}

export interface CalculatorTierMinimumLevel {
  tier: 0 | 1 | 2;
  minimum_level: number;
}

export type HarnessDisciplineId="pyrokinesis"|"cryokinesis"|"psychokinesis"|"electrokinesis";
export type HarnessDamageType="discipline"|"cold"|"fire"|"force"|"lightning"|"psychic";
export type HarnessSize="tiny"|"small"|"medium"|"large"|"huge"|"gargantuan";
export type HarnessControlOutcome="attack_disadvantage"|"forced_movement"|"movement_option_denial"|"reaction_denial"|"speed_reduction"|"speed_zero";
export type HarnessCondition="blinded"|"charmed"|"incapacitated"|"prone"|"restrained"|"stunned";

export interface HarnessMastery {
  kind:"graze"|"slow"|"push"|"sap";
  damage?:"psionic_ability_modifier";
  damage_required?:boolean;
  maximum_size?:HarnessSize;
  control_outcomes:HarnessControlOutcome[];
}
export interface HarnessDiscipline {
  id:HarnessDisciplineId;
  damage_type:Exclude<HarnessDamageType,"discipline"|"psychic">;
  signature_save:CalculatorSave;
  mastery:HarnessMastery;
}
export interface HarnessTargeting {
  tier:0|1|2;
  kind:"fixed_additional"|"proficiency_bonus_additional"|"cluster_remainder";
  additional_targets?:number;
}
export interface HarnessControlTier {
  tier:0|1|2;
  application:"failed_save"|"no_save";
  save?:CalculatorSave|"discipline_signature";
  hit_gated?:boolean;
  control_on_reach?:boolean;
  conditions?:HarnessCondition[];
  outcomes?:HarnessControlOutcome[];
  maximum_size?:HarnessSize;
  required_creature_type?:"humanoid";
  repeat_saves?:number;
  repeat_save_disadvantage?:boolean;
  duration:"instantaneous"|"until_end_current_turn"|"until_start_next_turn"|"until_end_next_turn"|"one_minute_concentration"|"one_hour"|"eight_hours"|"twenty_four_hours";
}
export interface HarnessFeatureRule {
  entity_id:string;
  discipline_ids:HarnessDisciplineId[];
  damage_type:HarnessDamageType;
  repeatability:"unlimited"|"once_per_attack_action";
  ignore_resistance_tiers?:Array<0|1|2>;
  replaces_mastery?:boolean;
  requires_additional_target?:boolean;
  targeting_by_tier?:HarnessTargeting[];
  control_tiers?:HarnessControlTier[];
}
export interface HarnessMechanics {
  manifested_strike:{entity_id:"common_manifested_strike";damage_type_source:"discipline";holdout_damage_type:"force";holdout_damage_divisor:2;critical_dice_multiplier:2;attack_bonus:{base:number;components:Array<"psionic_ability_modifier"|"proficiency_bonus"|"psionic_focus">};save_dc:{base:number;components:Array<"psionic_ability_modifier"|"proficiency_bonus"|"psionic_focus">}};
  overload:{entity_id:"common_overload";blood_tax_per_tier:{base:number;proficiency_bonus_multiplier:number};tier_two_limit_per_attack_action:1};
  disciplines:HarnessDiscipline[];
  feature_rules:HarnessFeatureRule[];
}

export interface Calculator {
  default_feature_id: string;
  default_fighter_level: number;
  default_psionic_ability_modifier: number;
  fighter_level_minimum: number;
  fighter_level_maximum: number;
  psionic_ability_modifier_minimum: number;
  psionic_ability_modifier_maximum: number;
  proficiency_bonus_bands: CalculatorLevelBand[];
  psi_point_bands: CalculatorLevelBand[];
  psionic_focus_bands: CalculatorLevelBand[];
  manifested_strike_die_bands: CalculatorLevelBand[];
  tier_minimum_levels: CalculatorTierMinimumLevel[];
  harness_mechanics: HarnessMechanics;
  features: CalculatorFeature[];
}

export interface Topic { id: string; title: string; entity_ids: string[]; order: number }
export interface Category { id: string; label: string; order: number; default_topic_id: string; topics: Topic[] }
export interface VocabularyValue { id: string; label: string; order: number }

export type OnboardingDestination =
  | { kind: "onboarding_section"; section_id: string }
  | { kind: "category"; category_id: string }
  | { kind: "entity"; entity_id: string };

export interface OnboardingLink {
  id: string;
  title: string;
  description?: string;
  destination: OnboardingDestination;
}

export interface Onboarding {
  id: string;
  title: string;
  introduction: {
    summary: string;
    no_psi_note: string;
    orientation: string;
  };
  primary_paths: OnboardingLink[];
  disciplines: {
    id: string;
    title: string;
    cards: OnboardingLink[];
  };
  basic_turn: {
    id: string;
    title: string;
    steps: string[];
    reminders: string[];
    destinations: OnboardingLink[];
  };
  build_checklist: {
    id: string;
    title: string;
    items: OnboardingLink[];
  };
  glossary: {
    id: string;
    title: string;
    entries: Array<OnboardingLink & { definition: string }>;
  };
  next_destinations: {
    id: string;
    title: string;
    items: OnboardingLink[];
  };
}

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
  calculator: Calculator;
  navigation: { default_category_id: string; categories: Category[] };
  onboarding: Onboarding;
  audits?: Array<{id:string; assertion:string; subject_ids:string[]}>;
}

export interface Diagnostic { severity: "error" | "warning"; code: string; message: string; path?: string }
