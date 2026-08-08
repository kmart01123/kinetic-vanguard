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
export type HarnessControlDuration="instantaneous"|"until_end_current_turn"|"until_start_next_turn"|"until_end_next_turn"|"while_in_area"|"one_minute_concentration"|"one_hour"|"eight_hours";
export interface HarnessControlEffect {
  gate:"on_reach"|"on_failed_save"|"while_in_area";
  conditions?:HarnessCondition[];
  outcomes?:HarnessControlOutcome[];
  duration:HarnessControlDuration;
  target_role?:"primary"|"secondary"|"all";
  requires_condition?:HarnessCondition;
}
export interface HarnessControlTier {
  tier:0|1|2;
  application:"failed_save"|"no_save";
  save?:CalculatorSave|"discipline_signature";
  hit_gated?:boolean;
  effects:HarnessControlEffect[];
  maximum_size?:HarnessSize;
  required_creature_type?:"humanoid";
  repeat_save_trigger?:"start_of_affected_turn";
  repeat_save_disadvantage?:boolean;
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
  armor_class_reduction_by_tier?:Array<{tier:0|1|2;value:number}>;
  damage_repetition?:"remaining_round_starts";
  damage_timing?:"start_of_affected_turn_after_repeat_save";
  starts_persistent_zone?:boolean;
  control_tiers?:HarnessControlTier[];
}
export type ControlEventV2="declaration"|"hit"|"entry"|"start_turn"|"save"|"repeat_save"|"exit"|"instantaneous_resolution";
export type ControlMovementModeV2="walk"|"fly"|"swim"|"climb"|"burrow";
export type ControlDispositionV2="modeled"|"excluded_by_profile"|"unsupported_error";
export type ControlDurationV2=
  |{kind:"instantaneous"}
  |{kind:"relative";owner:"controller"|"target";anchor:"start_turn"|"end_turn";offset_turns:number}
  |{kind:"while_in_area";area_id:string}
  |{kind:"concentration";maximum_value:number;unit:"round"|"minute"|"hour"};
export type ControlMagnitudeV2=
  |{kind:"condition";condition:string}
  |{kind:"forced_movement";distance_feet:number;distance_mode:"exact"|"up_to";movement_mode:"push"|"pull"|"reposition"|"lift";direction:string;path:string}
  |{kind:"speed_reduction";reduction:{kind:"flat_feet";value:number}|{kind:"fraction";numerator:number;denominator:number}|{kind:"terrain_multiplier";value:number};movement_modes:ControlMovementModeV2[]}
  |{kind:"speed_zero";movement_modes:ControlMovementModeV2[]}
  |{kind:"attack_disadvantage";scope:"next_attack"|"all_attacks";count?:number}
  |{kind:"reaction_denial";scope:"all_reactions"}
  |{kind:"movement_option_denial";movement_modes:ControlMovementModeV2[]}
  |{kind:"numerical_modifier";target:string;value:number};
export interface ControlComponentV2 {
  component_id:string;
  target_selector_ids:string[];
  magnitude:ControlMagnitudeV2;
  duration:ControlDurationV2;
  cadence:{apply:ControlEventV2[];repeat:ControlEventV2[];end:ControlEventV2[]};
  stacking:{key:string;mode:"stacks"|"nonstacking"|"replace"|"dominates"|"independent";refresh:"duration"|"none";replacement_group?:string;dominates_component_ids:string[]};
}
export interface ControlAreaV2 {
  area_id:string;
  shape:"sphere"|"cylinder"|"cone"|"line";
  origin:"controller"|"primary_target"|"selected_point"|"departure_or_arrival";
  radius_feet?:number;
  height_feet?:number;
  length_feet?:number;
  width_feet?:number;
  persistent:boolean;
  triggers:ControlEventV2[];
  exit_behavior:"ends_area_effects"|"none";
}
export interface ControlTargetSelectorV2 {
  selector_id:string;
  role:"primary"|"secondary"|"all";
  count:{kind:"fixed"|"up_to"|"proficiency_bonus"|"cluster_remainder"|"weighted_slots";value?:number;slots?:number;size_costs?:Record<string,number>};
  range:{feet:number;origin:"controller"|"primary_target"|"selected_point"|"departure_or_arrival"};
  restrictions:Array<{kind:string;value:string}>;
  gate_scope:"independent_per_target"|"shared";
  area?:ControlAreaV2;
}
export interface ControlBranchV2 {branch_id:string;outcome:"attack_hit"|"attack_miss"|"save_success"|"save_failure"|"no_save"|"other";applies:string[];replaces:string[];terminates:string[];refreshes:string[]}
export type ControlResolutionBodyV2=
  |{kind:"attack_roll";branches:ControlBranchV2[]}
  |{kind:"saving_throw";ability:CalculatorSave|"discipline_signature";branches:ControlBranchV2[]}
  |{kind:"no_save";branches:ControlBranchV2[]}
  |{kind:"other";branches:ControlBranchV2[]};
export interface ControlResolutionV2 {
  gate_id:string;
  selector_ids:string[];
  trigger:ControlEventV2;
  gate_scope:"independent_per_target"|"shared";
  resolution:ControlResolutionBodyV2;
}
export type ControlConcentrationV2=
  |{kind:"none"}
  |{kind:"required";startup:"on_resolution";occupancy:"one_controller_slot";replacement:"new_effect_ends_existing";maximum_duration:{value:number;unit:"round"|"minute"|"hour"};termination:Array<"failed_concentration_save"|"controller_incapacitated"|"controller_death"|"duration_expires"|"voluntary_end">};
export interface ControlTierModelV2 {
  effect_id:string;
  inheritance:{kind:"none"}|{kind:"resolved";source_tier:0|1|2};
  policy:{activation:"action"|"bonus_action"|"reaction"|"on_hit"|"passive";declaration:ControlEventV2;delivery:"attack_rider"|"standalone";psi_cost:number;overload_tier:0|1|2;blood_tax:"none"|"tier_formula";repeatability:"unlimited"|"once_per_attack_action"|"once_per_turn"|"limited_use";mastery:"stacks"|"replaces_on_declaration"|"not_applicable"};
  target_selectors:ControlTargetSelectorV2[];
  components:ControlComponentV2[];
  resolutions:ControlResolutionV2[];
  concentration:ControlConcentrationV2;
  relationships:{replacement_groups:Array<{group_id:string;component_ids:string[]}>;dominance:Array<{dominant_component_id:string;suppressed_component_ids:string[]}>};
}
export type ControlLedgerEntryV2=
  |{entity_id:string;tier:0|1|2;disposition:"modeled";model:ControlTierModelV2}
  |{entity_id:string;tier:0|1|2;disposition:"excluded_by_profile";profile_id:string;reason:"selectable_advanced_training_disabled"|"outside_headline_control_value"|"incoming_enemy_attacks_unmodeled"}
  |{entity_id:string;tier:0|1|2;disposition:"unsupported_error";reason:"pending_authority_population"};
export interface ControlAuthorityV2 {
  contract_version:"2.0.0";
  active_profile:{id:string;selectable_advanced_training:"excluded";tactical_master:"included";legendary_resistance:"metadata_only";unsupported_disposition:"error"};
  target_data_requirements:Array<"walking_speed"|"movement_modes"|"hover"|"nonvisual_senses">;
  policy_inputs:{horizon_rounds:number;action_economy:{attack_rider_declaration:"before_attack_roll";standalone_action_limit_per_turn:1;action_surge_additional_standalone:false};resources:{psi_source:"psi_point_bands";blood_tax_source:"harness_overload";tier_two_limit_per_attack_action:1};concentration:{pressure:"endogenous_only";startup_blood_tax_check:"exempt";occupancy:"one_controller_slot";replacement:"new_effect_ends_existing";termination:Array<"failed_concentration_save"|"controller_incapacitated"|"controller_death"|"duration_expires"|"voluntary_end">}};
  masteries:Array<{mastery_id:string;minimum_level:number;trigger:ControlEventV2[];component:ControlComponentV2}>;
  tactical_master:{minimum_level:9;choice_mastery_ids:string[];choice_timing:"declaration";behavior:"replaces_kinetic_mastery"};
  ledger:ControlLedgerEntryV2[];
}
export interface HarnessMechanics {
  action_economy:{standalone_psionic_action_limit_per_turn:1;action_surge_allows_additional_standalone_psionic_action:false};
  manifested_strike:{entity_id:"common_manifested_strike";damage_type_source:"discipline";holdout_damage_type:"force";holdout_damage_divisor:2;critical_dice_multiplier:2;attack_bonus:{base:number;components:Array<"psionic_ability_modifier"|"proficiency_bonus"|"psionic_focus">};save_dc:{base:number;components:Array<"psionic_ability_modifier"|"proficiency_bonus"|"psionic_focus">}};
  overload:{entity_id:"common_overload";blood_tax_per_tier:{base:number;proficiency_bonus_multiplier:number};tier_two_limit_per_attack_action:1;mastery:{minimum_level:18;uses_per_rest:1;blood_tax_divisor:2;minimum_per_overload:1}};
  disciplines:HarnessDiscipline[];
  feature_rules:HarnessFeatureRule[];
  control_authority_v2:ControlAuthorityV2;
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
