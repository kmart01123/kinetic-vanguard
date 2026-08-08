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

export type DamageHarnessDisciplineId="pyrokinesis"|"cryokinesis"|"psychokinesis"|"electrokinesis";
export type DamageHarnessDamageType="discipline"|"cold"|"fire"|"force"|"lightning"|"psychic";
export type ControlConditionV2="blinded"|"charmed"|"incapacitated"|"prone"|"restrained"|"stunned";

export interface DamageHarnessDiscipline {
  id:DamageHarnessDisciplineId;
  damage_type:Exclude<DamageHarnessDamageType,"discipline"|"psychic">;
  signature_save:CalculatorSave;
  graze_damage?:"psionic_ability_modifier";
}
export interface DamageHarnessTargeting {
  tier:0|1|2;
  kind:"fixed_additional"|"proficiency_bonus_additional"|"cluster_remainder";
  additional_targets?:number;
}
export interface DamageHarnessFeatureRule {
  entity_id:string;
  discipline_ids:DamageHarnessDisciplineId[];
  damage_type:DamageHarnessDamageType;
  repeatability:"unlimited"|"once_per_attack_action";
  ignore_resistance_tiers?:Array<0|1|2>;
  requires_additional_target?:boolean;
  targeting_by_tier?:DamageHarnessTargeting[];
  armor_class_reduction_by_tier?:Array<{tier:0|1|2;value:number}>;
  damage_repetition?:"remaining_round_starts";
  damage_timing?:"start_of_affected_turn_after_repeat_save";
  starts_persistent_zone?:boolean;
}
export type ControlEventV2=
  |{kind:"declaration"|"activation"|"hit"|"save"|"damage_context"|"concentration_end"|"instantaneous_resolution"}
  |{kind:"turn";owner:"controller"|"target";turn_anchor:"start"|"end"|"during"}
  |{kind:"turn";owner:"triggering_turn";turn_anchor:"end"}
  |{kind:"entry";owner:"any_creature";turn_anchor:"during_turn"}
  |{kind:"exit";owner:"target";turn_anchor:"during_turn"};
export type ControlMovementModeV2="walk"|"fly"|"swim"|"climb"|"burrow";
export type ControlSaveAbilityV2=CalculatorSave|"wisdom"|"discipline_signature";
export type ControlDispositionV2="modeled"|"excluded_by_profile";
export type ControlDurationV2=
  |{kind:"instantaneous"}
  |{kind:"relative";owner:"controller"|"target";anchor:"start_turn"|"end_turn";offset_turns:number}
  |{kind:"relative";owner:"triggering_turn";anchor:"end_turn";offset_turns:0}
  |{kind:"while_in_area";area_id:string}
  |{kind:"concentration";maximum_value:number;unit:"round"|"minute"|"hour"};
export type ControlMagnitudeV2=
  |{kind:"condition";condition:ControlConditionV2}
  |{kind:"forced_movement";distance_feet:number;distance_mode:"exact"|"up_to";movement_mode:"push"|"pull"|"reposition"|"lift";reference_point:"controller"|"primary_target"|"selected_point"|"target_current_position";axis:"horizontal"|"vertical"|"any";direction:"away_from_reference"|"toward_reference"|"controller_choice"|"vertical_up";destination:{selection:"controller_choice"|"rule_determined";visibility:"required"|"not_required";occupancy:"unoccupied_required"|"not_specified"};path:{line:"straight"|"not_required";blocked:"nearest_unoccupied_along_path"|"movement_not_permitted"|"not_specified"};resolution_order:"controller_selected"|"independent"}
  |{kind:"speed_reduction";reduction:{kind:"flat_feet";value:number}|{kind:"fraction";numerator:number;denominator:number}|{kind:"terrain_multiplier";value:number};movement_modes:ControlMovementModeV2[]}
  |{kind:"speed_zero";movement_modes:ControlMovementModeV2[]}
  |{kind:"difficult_terrain";scope:"area";movement_cost_multiplier:2}
  |{kind:"persistent_elevation";state:"hovering";position_reference:"current_position"}
  |{kind:"fall";origin:"current_position"}
  |{kind:"attack_disadvantage";scope:"next_attack"|"all_attacks";count?:number}
  |{kind:"reaction_denial";scope:"all_reactions"}
  |{kind:"movement_option_denial";movement_modes:ControlMovementModeV2[]}
  |{kind:"numerical_modifier";target:"armor_class";value:number};
export interface ControlComponentV2 {
  component_id:string;
  target_selector_ids:string[];
  magnitude:ControlMagnitudeV2;
  duration:ControlDurationV2;
  cadence:{apply:ControlEventV2[];repeat:ControlEventV2[];end:ControlEventV2[]};
  stacking:{key:string;mode:"stacks"|"nonstacking"|"replace"|"dominates"|"independent";refresh:"duration"|"none";replacement_group?:string;dominates_component_ids:string[]};
  choice_requirement?:{choice_id:string;option_id:string};
}
export type ControlAreaPlacementV2=
  |{kind:"controller"}
  |{kind:"primary_target"}
  |{kind:"selected_point";range:{feet:number;origin:"controller"};stationary:boolean}
  |{kind:"endpoint_choice";choice_id:string;departure:{origin:"controller_current_space"};arrival:{range:{feet:number;origin:"departure_space"};visibility:"required";occupancy:"unoccupied_required"}};
export type ControlAreaV2={
  area_id:string;
  shape:"sphere"|"cylinder"|"cone"|"line";
  placement:ControlAreaPlacementV2;
  radius_feet?:number;
  height_feet?:number;
  length_feet?:number;
  width_feet?:number;
  triggers:ControlEventV2[];
  exit_behavior:"ends_area_effects"|"none";
}&(
  |{persistent:true;entry_policy:{frequency:"once_per_turn";moved_area_counts_as_entry:boolean};movement:{kind:"stationary"}|{kind:"controller_reposition";controller_action:"bonus_action";timing:{kind:"turn";owner:"controller";turn_anchor:"during"};distance_feet:number;distance_mode:"up_to"}}
  |{persistent:false;entry_policy?:never;movement?:never}
);
export interface ControlTargetSelectorV2 {
  selector_id:string;
  role:"primary"|"secondary"|"all";
  selection:"controller_choice"|"all_in_area"|"automatic";
  count:{kind:"fixed"|"up_to"|"up_to_proficiency_bonus"|"all_eligible"|"weighted_slots";value?:number;slots?:number;size_costs?:Partial<Record<"tiny"|"small"|"medium"|"large",number>>};
  range:{kind:"distance";feet:number;origin:"controller"|"primary_target"}|{kind:"area"};
  restrictions:ControlTargetRestrictionV2[];
  gate_scope:"independent_per_target"|"shared";
  area?:ControlAreaV2;
}
export type ControlTargetRestrictionV2=
  |{kind:"visibility";requirement:"controller_can_see"}
  |{kind:"maximum_size";size:"large_or_smaller"}
  |{kind:"unique_targets";required:true}
  |{kind:"excludes_primary_target";required:true};
export interface ControlBranchV2 {branch_id:string;outcome:"attack_hit"|"attack_miss"|"save_success"|"save_failure"|"no_save"|"damage_context"|"other";applies:string[];replaces:string[];terminates:string[];refreshes:string[];next_gate_ids:string[]}
export type ControlResolutionBodyV2=
  |{kind:"attack_roll";branches:ControlBranchV2[]}
  |{kind:"saving_throw";ability:ControlSaveAbilityV2;role:"initial"|"repeat"|"recurring";mode:"normal"|"advantage"|"disadvantage";branches:ControlBranchV2[]}
  |{kind:"no_save";branches:ControlBranchV2[]}
  |{kind:"damage_context";branches:ControlBranchV2[]}
  |{kind:"other";branches:ControlBranchV2[]};
export interface ControlResolutionV2 {
  gate_id:string;
  selector_ids:string[];
  requires_active_component_ids?:string[];
  trigger:ControlEventV2;
  gate_scope:"independent_per_target"|"shared";
  resolution:ControlResolutionBodyV2;
}
export type ControlConcentrationV2=
  |{kind:"none"}
  |{kind:"required";startup:"on_activation"|"on_hit"|"on_resolution";occupancy:"one_controller_slot";replacement:"new_effect_ends_existing";maximum_duration:{value:number;unit:"round"|"minute"|"hour"};termination:Array<"failed_concentration_save"|"controller_incapacitated"|"controller_death"|"duration_expires"|"voluntary_end">};
export interface ControlChoiceV2 {
  choice_id:string;
  kind:"mode"|"placement";
  timing:ControlEventV2;
  resolution:"once_per_effect";
  scope:"all_targets"|"area_origin";
  options:string[];
}
export interface ControlTierModelV2 {
  effect_id:string;
  inheritance:{kind:"none"}|{kind:"resolved";source_tier:0|1|2};
  policy:{activation:"action"|"bonus_action"|"reaction"|"on_hit"|"passive";declaration:ControlEventV2;delivery:"attack_rider"|"standalone";psi_cost:number;overload_tier:0|1|2;blood_tax:"none"|"tier_formula";repeatability:"unlimited"|"once_per_attack_action"|"once_per_turn"|"limited_use";mastery:"stacks"|"replaces_on_declaration"|"not_applicable"};
  choices:ControlChoiceV2[];
  target_selectors:ControlTargetSelectorV2[];
  components:ControlComponentV2[];
  root_gate_ids:string[];
  resolutions:ControlResolutionV2[];
  concentration:ControlConcentrationV2;
  relationships:{replacement_groups:Array<{group_id:string;component_ids:string[]}>;dominance:Array<{dominant_component_id:string;suppressed_component_ids:string[]}>};
}
export type ControlLedgerEntryV2=
  |{entity_id:string;tier:0|1|2;disposition:"modeled";model:ControlTierModelV2}
  |{entity_id:string;tier:0|1|2;disposition:"excluded_by_profile";profile_id:string;reason:"selectable_advanced_training_disabled"|"outside_headline_control_value"|"incoming_enemy_attacks_unmodeled"};
export interface ControlAuthorityV2 {
  contract_version:"2.1.0";
  active_profile:{id:string;selectable_advanced_training:"excluded";tactical_master:"included";legendary_resistance:"metadata_only";unsupported_disposition:"error"};
  target_data_requirements:Array<"walking_speed"|"movement_modes"|"hover"|"nonvisual_senses">;
  policy_inputs:{horizon_rounds:number;action_economy:{attack_rider_declaration:"before_attack_roll";standalone_action_limit_per_turn:1;action_surge_additional_standalone:false};resources:{psi_source:"psi_point_bands";blood_tax_source:"harness_overload";tier_two_limit_per_attack_action:1};concentration:{pressure:"endogenous_only";startup_blood_tax_check:"exempt";occupancy:"one_controller_slot";replacement:"new_effect_ends_existing";termination:Array<"failed_concentration_save"|"controller_incapacitated"|"controller_death"|"duration_expires"|"voluntary_end">}};
  masteries:Array<{mastery_id:string;minimum_level:number;trigger:ControlEventV2[];component:ControlComponentV2}>;
  tactical_master:{minimum_level:9;choice_mastery_ids:string[];choice_timing:ControlEventV2;behavior:"replaces_kinetic_mastery"};
  ledger:ControlLedgerEntryV2[];
}
export interface HarnessMechanics {
  action_economy:{standalone_psionic_action_limit_per_turn:1;action_surge_allows_additional_standalone_psionic_action:false};
  manifested_strike:{entity_id:"common_manifested_strike";damage_type_source:"discipline";holdout_damage_type:"force";holdout_damage_divisor:2;critical_dice_multiplier:2;attack_bonus:{base:number;components:Array<"psionic_ability_modifier"|"proficiency_bonus"|"psionic_focus">};save_dc:{base:number;components:Array<"psionic_ability_modifier"|"proficiency_bonus"|"psionic_focus">}};
  overload:{entity_id:"common_overload";blood_tax_per_tier:{base:number;proficiency_bonus_multiplier:number};tier_two_limit_per_attack_action:1;mastery:{minimum_level:18;uses_per_rest:1;blood_tax_divisor:2;minimum_per_overload:1}};
  disciplines:DamageHarnessDiscipline[];
  feature_rules:DamageHarnessFeatureRule[];
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
