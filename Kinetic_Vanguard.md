# Kinetic Vanguard Fighter

> **Version:** v12.1.0

*A mental-stat martial controller that channels elemental and telekinetic force through disciplined psionic projection.*

*Created by NixNinja in collaboration with AI assistants. Special thanks to various muses, great and small.*

# DESIGN NOTES

Kinetic Vanguard is built around three deliberate tensions: resource versus impact, power versus survivability, and identity versus flexibility. Psi Points keep you honest turn to turn — you cannot do everything every fight. Overload lets you spend health for power, which means the most dramatic moments cost something real. Your primary Discipline locks in your identity while Deflection Screen, Phase Step, and the Advanced Training features give you a universal toolkit beyond your discipline.

The subclass rewards players who think one turn ahead. Knowing when to Overload, when to hold Psi for Deflection Screen, and when to conserve is more interesting than any individual feature. The Blood Tax scales with your Proficiency Bonus — the pain you accept grows with you.

# CLIFF NOTES

|                                        |                                                                                                                                                                                                                                                                                                                                                                                                                           |
|----------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Mental-stat Fighter.**               | Your attack rolls, damage, and save DCs all run off Intelligence, Wisdom, or Charisma. Pick one at 3rd and never look back.                                                                                                                                                                                                                                                                                               |
| **Short-rest resource.**               | Psi Points = half Fighter level (rounded up) + Proficiency Bonus. They refuel on a short or long rest — enough for meaningful choices without feeling stingy.                                                                                                                                                                                                                                                                     |
| **Manifested Strike is your attack.**  | Replace a weapon attack with a special ranged psionic attack (60 ft). For feats, Fighting Styles, and other features that reference ranged weapons or attacks made with them, treat it as an attack made with a ranged weapon with which you are proficient. This includes the SRD Archery Fighting Style feat. It is not a weapon, spell, or object for any other purpose. Discipline riders attach to its hits. |
| **Overload is your throttle.**         | Before the roll, declare one rider and its Overload tier. Psi and Blood Tax are spent on declaration. On a hit, the package resolves; on a miss, the rider does not resolve, but the costs remain spent. Manifested Strike itself is never Overloaded and never generates Blood Tax. Effects that explicitly trigger on a miss, such as Graze, still resolve.                                                             |
| **Your Discipline is your identity.**  | Pyrokinesis melts the boss. Electrokinesis kills the room. Cryokinesis stops the room. Psychokinesis rearranges it. Five features across twenty levels. Your Signature Rider costs 0 Psi on every use and can be applied to any number of your Manifested Strike hits.                                                                                                                                                    |
| **Advanced Training is your toolkit.** | Deflection Screen (5th) gives you a reaction damage soak. Phase Step (10th) gives you bonus action teleportation. At 15th, 18th, and 20th, you pick three of eight Advanced Training features — a psychic damage nuke, a mental control rider, a mental influence tool, a gravity zone, a barrier, a teleporting detonation, an extra Overload Mastery use, or an expanded Psi pool. Swappable on level-up.               |

> **Abbreviations** MS — Manifested Strike · Psi mod — Psionic Ability modifier · BT — Blood Tax (psychic self-damage from Overloading) · OL — Overload (Tier 1 or Tier 2 escalation) · PB — Proficiency Bonus · Psi — Psi Points (short-rest resource pool) · T0 / T1 / T2 — Tier 0 (base) / Tier 1 / Tier 2 Overload

# HOW TO PLAY THIS SUBCLASS

On your turn, when you attack with Manifested Strike, your Discipline’s 3rd-level rider is your Signature Rider and costs 0 Psi on every use, even if Overloaded; Blood Tax still applies. Higher-level riders cost their listed Psi. Before each attack roll, declare the rider and its Overload tier. Each hit can carry one rider, and different hits can carry different riders. Any Psi cost and Blood Tax are spent on declaration. On a hit, the declared package resolves; on a miss, the rider does not resolve, but the committed costs remain spent. Manifested Strike itself uses the die set by your Fighter level and is never Overloaded.

Resolve attacks one at a time. Immediately before each attack roll, choose its target and declare that attack’s complete package, including any rider, Overload tier, and damage-type option. Pay all associated Psi and Blood Tax at that time, then roll and fully resolve the attack before declaring the next attack. You do not declare or pay for later attacks in the Attack action in advance. Any unused attacks may target different creatures and use different legal packages based on the battlefield after earlier attacks resolve. Per-Attack-action limits remain spent once used.

**Interactive Sheet Execution:** Each legal attack appears as a separate swing row. An unfired row remains editable. Pressing **Execute Swing** snapshots and rolls that swing once, logs the natural die, applicable modifiers, final attack total, damage, costs, and rider information, then locks and greys out the entire row except for its outcome controls. The sheet does not require or infer creature Armor Class. Before firing, the attack outcome is **Unresolved**; after an attack-roll swing fires, it defaults to **Hit** and may be corrected to **Miss** after table adjudication. Creature-save outcomes remain **Unresolved** until the table supplies the result. Outcome edits may update deterministic effect text but never reroll the swing. **Undo Last Swing** applies only to the most recently fired swing, is itself logged, and reopens only that row.

**Short Disruption Timing:** Unless a feature says otherwise, reaction denial and attack-roll disadvantage imposed by an instantaneous Kinetic Vanguard feature last until the start of your next turn. Hard control conditions use the duration stated by the feature. Zones and recurring-save effects use their own timing.

A rider is an on-hit feature declared as part of a Manifested Strike. Passive and triggered features are not riders unless their text says otherwise. Advanced Training riders include Mind Shred and Mind Lock. A hit can carry either one Discipline rider or one Advanced Training rider, never both. Any rider that uses Manifested Strike dice uses the base die for your Fighter level.

**Rider Target Parity:** When a rider creates a chain, arc, burst, Sphere, or other multi-creature effect centered on or originating from the creature struck by Manifested Strike, the struck creature is included among the rider's affected creatures unless the feature's geometry makes a particular effect impossible. Every affected creature resolves the same rider damage, saving throw, conditions, and other applicable effects. A feature may limit how many additional creatures are affected, but the struck creature does not receive a stronger or weaker version of the rider package merely because it was struck.

Attack Riders and Standalone Actions: You may mix weapon attacks and Manifested Strikes in any order within the Attack action. Each Manifested Strike can carry one rider. Your Signature Rider costs 0 Psi and can be used on any number of Manifested Strike hits in an Attack action; every other attack rider can be used once per Attack action and costs its listed Psi. Different riders may be attached to different hits. Only one rider in each Attack action may be Overloaded to Tier 2. Action Surge creates a new Attack action and refreshes these per-Attack-action limits. You may activate only one standalone psionic feature whose activation requires an Action on each of your turns; Action Surge can still grant another Attack action, but cannot be used to activate a second standalone psionic Action feature. Unless a feature says otherwise, damage from a hit resolves before any saving throw rider tied to that hit.

Your Discipline defines your identity across five features. Deflection Screen (5th) and Phase Step (10th) are universal psionic tools granted to every Vanguard. Advanced Training III, IV, and V (15th, 18th, and 20th) let you pick three of eight high-tier techniques regardless of discipline.

# 01 OVERLOAD TIER SYSTEM

Overload is a deliberate escalation that trades hit points for power. It applies to your techniques — riders and standalone psionic features — and never to Manifested Strike itself: the strike cannot be Overloaded and never generates Blood Tax. An Overload is declared when you declare the feature it escalates — for a rider, before the attack roll. Two tiers exist, both gated by Fighter level. As a general principle, Overload tiers are cumulative: Tier 2 includes every effect of Tier 1 unless it explicitly replaces it (some riders say “instead” to swap an effect rather than stack it). Each tier’s text states whether it adds to or replaces the lower tier’s effect.

> **The Blood Tax**
>
> **Tier 1 Overload (3rd level):** You may Overload a rider or standalone feature to Tier 1, gaining the effect listed in its text. You take psychic self-damage equal to your Proficiency Bonus (Blood Tax), paid when you declare the Overload, whether or not the attack hits.
>
> **Tier 2 Overload (10th level): You may Overload a rider or standalone feature to Tier 2, gaining the effects listed in its text. Within each Attack action, only one rider can be Tier 2. Action Surge creates a new Attack action and a fresh Tier 2 rider window. This rider limit does not restrict standalone features.**
>
> *The full attack package — rider activation and rider Overload tier — is declared before the roll. One rider per hit (discipline or Advanced Training). A hit resolves the whole package. A miss cancels rider effects, but Psi and Blood Tax are still spent — Blood Tax is paid immediately on declaration, never after the attack resolves. If you Overload more than one feature in the same turn (a rider and a standalone feature, say), you pay Blood Tax once per Overload declared.*
>
> **⚠** Declare the full package before the roll — one rider and its Overload tier. Hit: everything resolves. Miss: Psi AND Blood Tax are still spent; no effects. (Exception: effects that explicitly trigger on a miss, such as the Graze mastery, still resolve.)
>
> ⚠ Blood Tax is psychic damage. Resistance to psychic damage halves it normally. Immunity to psychic damage treats it as Resistance against Blood Tax instead of preventing it. Regardless of the source of reduction, you take at least half the declared Blood Tax, rounded down, unless Overload Mastery specifically says otherwise.

**Attack Declaration Costs**

| Declaration                          | Psi                                 | Blood Tax      | Notes                                                                        |
|--------------------------------------|-------------------------------------|----------------|------------------------------------------------------------------------------|
| MS (no rider)                        | 0                                   | None           | Always available                                                             |
| MS + T0 rider                        | Listed cost (0 for Signature Rider) | None           | Signature Rider is unlimited; other attack riders are once per Attack action |
| MS + T1 rider                        | Listed cost (0 for Signature Rider) | PB             | Paid on declaration, hit or miss                                             |
| MS + T2 rider                        | Listed cost (0 for Signature Rider) | 2×PB           |                                                                              |
| Overloaded standalone feature        | Feature cost                        | Per its tier\* |                                                                              |
| Rider OL + standalone OL (same turn) | Rider cost + feature cost           | Sum both\*     | Two Blood Taxes                                                              |

*\*Blood Tax per tier: PB at Tier 1, 2×PB at Tier 2. Each Overload declared pays independently — an Overloaded rider plus an Overloaded standalone feature in the same turn means two separate Blood Taxes. Any Psi cost and Blood Tax are spent on declaration (hit or miss). T0 riders cost their listed Psi but no HP; Signature Riders cost 0 Psi at every tier. Only T1+ Overloads incur Blood Tax. Manifested Strike itself never appears in this math — it cannot be Overloaded.*

**Blood Tax per Overload declared: Tier 1 = PB. Tier 2 = 2×PB. Sum all Overloads in the sequence.**

*Tier 2 costs 2×PB because it includes Tier 1’s PB plus PB more. T0 riders cost 0 HP. A double-Overload turn (e.g., a Tier 1 Vectored Thrust plus a Tier 2 rider) pays each Overload separately.*

**Manifested Strike die by level:** 1d6 (3rd–4th) → 1d8 (5th–10th) → 1d10 (11th–16th) → 1d12 (17th–20th)

| Fighter Level | MS Die |
|---------------|--------|
| 3–4           | 1d6    |
| 5–10          | 1d8    |
| 11–16         | 1d10   |
| 17–20         | 1d12   |

**Critical Hits and Riders:** On a critical hit with Manifested Strike, double only the Manifested Strike's damage dice. Damage dice dealt by a rider are never doubled by a critical hit, regardless of whether the rider damages the struck creature, another creature, or multiple creatures. Flat damage, saving throws, conditions, forced movement, and all other rider effects resolve normally. Standalone features are not riders and are unaffected by this rule.

**Using Overload: For a rider, declare the rider and its tier before the attack roll. A hit resolves the declared package; a miss does not resolve the rider, but Psi and Blood Tax remain spent. Standalone features are declared and paid for when activated.**

**Damage Immunity and Riders: Discipline riders deal your Discipline’s damage type unless stated otherwise. Advanced Training riders deal the damage type listed in their text. Damage immunity prevents only the matching damage; it does not skip the rider’s saving throw or other effects. For example, a cold-immune creature can still be Restrained by Snow Chains, and a fire-immune creature can still be Blinded by Flare.**

> **Concentration Startup Exception:** The Blood Tax from the activation that starts a concentration feature does not trigger a concentration check. Only subsequent Blood Tax and other damage sources require checks as normal. Standard concentration rules still apply — you can only concentrate on one feature at a time.
>
> **Blood Tax and Temporary Hit Points:** Blood Tax bypasses Temporary Hit Points and is deducted directly from your current Hit Points. Temporary Hit Points cannot absorb, reduce, or pay Blood Tax. Blood Tax remains psychic damage for Resistance, concentration checks, and effects that trigger when you take damage.
>
> **Blood Tax at 0 Hit Points:** Blood Tax is paid before the declared attack or feature resolves. If it reduces you to 0 hit points, you fall Unconscious immediately and the declared attack or feature does not resolve. Any Psi spent and Blood Tax paid remain spent.
>
> **Example — Level 11 Cryokinesis (PB 4, Int +3)**
>
> *Before rolling, you declare: “Glacial Spike T2.”*
>
> Your strike uses its level-set die: 1d10. The Tier 2 declaration is on Glacial Spike — the strike itself can never be Overloaded.
>
> Hit: Manifested Strike deals 1d10 + 3, and Glacial Spike adds 2 cold damage, for 1d10 + 5 total. On a failed Con save, the target is Restrained until the end of your next turn.
>
> Blood Tax: 1 × 2 × PB = 2 × 4 = 8, paid on declaration. Glacial Spike is a Signature Rider and costs 0 Psi; Tier 2 escalates its control.
>
> Miss: No effects; Blood Tax (8) is still paid — it was spent on declaration. Glacial Spike costs 0 Psi. Roll your next attack.
>
> Example — Full Attack Turn, Level 11 Pyrokinesis (PB 4, Cha +4, MS 1d10, 3 attacks)
>
> You have 10 Psi. Three attacks this turn. You want focused damage.
>
> Attack 1: MS + Ember Bolt T2 (Signature Rider) — Declare: “Ember Bolt T2.” Psi: 0. On hit: 1d10 + 4 plus 6 fire damage (average 15.5). Blood Tax: 2×PB = 8, paid on declaration.
>
> Attack 2: MS + Cinder Lance T0 — Declare: “Cinder Lance.” Psi: 3. On hit: the strike deals 1d10 + 4 and Cinder Lance adds 2 base MS dice, for 3d10 + 4 fire damage (average 20.5). Blood Tax: 0.
>
> Attack 3: MS + Ember Bolt T0 — Declare: “Ember Bolt.” Psi: 0. On hit: 1d10 + 4 plus 2 fire damage (average 11.5). Blood Tax: 0.
>
> Turn totals (all three hit): Psi: 3 of 10. Blood Tax: 8. Average damage to the primary target: 47.5 fire. A miss still spends any committed Psi and Blood Tax.
>
> **Example — Sustained Turn, Level 11 Psychokinesis (PB 4, Int +4, MS 1d10, 3 attacks)**
>
> *You have 10 Psi. No need to nova — control the board.*
>
> **Bonus Action: Vectored Thrust T1 Overload** — Psi: 2. Effect: Fly speed 30 ft, no opportunity attacks (Concentration, up to 10 min). Blood Tax: 1 × PB = 4 (standalone — paid on activation, no roll).
>
> **Attack 1: MS + T0 Telekinetic Shove (Signature Rider) — Declare: “Telekinetic Shove.” Psi: 0. On hit: avg 11.5 force (1d10+4 plus Shove’s fixed +2), with a Str save against the 10-ft directional push. Blood Tax: 0.**
>
> **Attack 2: MS** — On hit: avg 9.5 force. Blood Tax: 0.
>
> **Attack 3: MS** — On hit: avg 9.5 force. Blood Tax: 0.
>
> **Turn totals:** Psi: 2 of 10. BT = 4 (Vectored Thrust T1). Damage: 30.5 force on average, one target repositioned, flying. Sustainable with occasional VT refresh.
>
> **Example — Lockdown Turn, Level 11 Cryokinesis (PB 4, Int +4, MS 1d10, 3 attacks)**
>
> *You have 10 Psi. Frozen Ground is already active (2 Psi spent last turn).*
>
> **Attack 1: MS + T0 Glacial Spike (Signature Rider) — Declare: “Glacial Spike.” Psi: 0. On hit: avg 11.5 cold (1d10+4 plus Spike’s fixed +2). Target Speed −10 ft until the end of your next turn. Blood Tax: 0.**
>
> **Attack 2: MS + T1 Glacial Spike** — Declare: “Glacial Spike T1.” Psi: 0. On hit: avg 11.5 cold. On a failed Con save, the target’s Speed becomes 0; on a successful save, the Tier 0 −10-foot reduction remains. Blood Tax: PB = 4, paid on declaration; a miss still spends the Blood Tax.
>
> **Attack 3: MS** — On hit: avg 9.5 cold. Blood Tax: 0.
>
> **Turn totals: Psi: 0. BT = 4 (Glacial Spike T1). Damage: 32.5 cold on average. The target likely has Speed 0 in difficult terrain; Frozen Ground can stop its movement on its turn. Low burn, high lockdown.**

# 02 CORE FEATURES

**Psionic Discipline** · *3rd Level · Passive*

Choose one of the following as your Psionic Ability: Intelligence, Wisdom, or Charisma. You use your Psionic Ability for Manifested Strike attack and damage rolls, saving throw DCs, and all subclass features that reference your Psionic Ability.

**Psionic save DC** = 8 + Proficiency Bonus + Psionic Ability modifier

**Discipline Signature Save** · *3rd Level · Passive*

Each Discipline has one signature saving throw, used by any feature that calls for your “signature save” (such as Improved Phase Step). Pyrokinesis uses Dexterity, Cryokinesis uses Constitution, Psychokinesis uses Strength, and Electrokinesis uses Charisma. This is the saving throw the target makes against those features; it does not change any save another feature already specifies.

**Psi Reservoir** · *3rd Level · Short/Long Rest*

Your Psi Points equal half your Fighter level (rounded up) + your Proficiency Bonus. You regain all expended Psi Points on a short or long rest.

| Fighter Level | Proficiency Bonus | Psi Points |
|---------------|-------------------|------------|
| 3–4           | +2                | 4          |
| 5–6           | +3                | 6          |
| 7–8           | +3                | 7          |
| 9–10          | +4                | 9          |
| 11–12         | +4                | 10         |
| 13–14         | +5                | 12         |
| 15–16         | +5                | 13         |
| 17–18         | +6                | 15         |
| 19–20         | +6                | 16         |

**Psionic Link** · *3rd Level · Passive*

You can communicate telepathically with one or more creatures you can see within 60 feet, provided you share a common language with each creature. When you address multiple creatures, each receives the same message. A recipient can reply telepathically to you, but recipients cannot communicate directly with one another through this feature. This communication does not grant mind reading.

**Manifested Strike** · *3rd Level · Attack Action*

When you take the Attack action, you can replace any number of your weapon attacks with a Manifested Strike. A Manifested Strike is a special ranged psionic attack with a range of 60 feet, formed from psionic force. Your Discipline determines its damage type. Add your Psionic Ability modifier to Manifested Strike damage. Your Manifested Strike attack bonus is your Psionic Ability modifier + your Proficiency Bonus + your Psionic Focus bonus. **Your Psionic Focus bonus is +1 at Fighter levels 3–8, +2 at levels 9–16, and +3 at levels 17–20.** On a critical hit, double only the Manifested Strike's damage dice; rider damage dice never double. The damage die scales with Fighter level per the table in Section 01. For the purposes of feats, Fighting Styles, and other features that reference ranged weapons or attacks made with them, treat Manifested Strike as an attack made with a ranged weapon with which you are proficient. It is not a weapon, spell, or object for any other purpose. Manifested Strike is, however, a magical effect: creatures with Magic Resistance (or a similar trait) have advantage on saving throws forced by your riders, though the strike’s attack roll and damage are unaffected. Manifested Strike itself costs no Psi — you can always attack.

**Somatic Requirement:** You project Manifested Strike from one of your hands. To make the attack, you must have the free use of that hand to perform the psionic gesture and release the strike. A hand is free for this purpose if it is not holding or manipulating a weapon, Shield, object, or creature. You can release one hand from a Two-Handed weapon, make the Manifested Strike, and re-grip the weapon before a later attack in the same Attack action; releasing or replacing a hand on a weapon you continue to hold requires no action and does not equip or unequip that weapon. Features delivered through Manifested Strike inherit this requirement unless their text says otherwise. The exact gesture is yours to describe, but the manifested force visibly originates from the gesturing hand. This is a psionic Somatic requirement; Manifested Strike remains a special psionic attack, not a spell.

**Sneak Attack:** Manifested Strike qualifies for the Rogue’s Sneak Attack feature as an attack made with a ranged weapon, provided all other Sneak Attack requirements are met. Sneak Attack damage dice double normally on a critical hit; they are not rider dice.

**Magical Effects:** For the purpose of Magic Resistance and similar effects, all Kinetic Vanguard features — Manifested Strike, every rider, and every standalone psionic feature — are magical effects. However, none is a spell and none is a Magic action: they cannot be Counterspelled, are unaffected by features that key off spellcasting, and Beguile in particular is a magical effect whose save is always Charisma but which is not a spell.

**Manifested Strike in Melee: Manifested Strike is a ranged attack. If a hostile creature that can see you and is not Incapacitated is within 5 feet of you, you have Disadvantage on the attack roll. Use Phase Step, Disengage, movement, a weapon attack, or another effect whose own text explicitly removes that ranged-attack pressure.**

**The Holdout Option — Force Damage: When you declare a Manifested Strike, you may have it deal force damage instead of your Discipline’s damage type. The strike then deals half damage, rounded down. Declare this before the attack roll with the rest of the attack package. Riders are unchanged: Discipline riders use the Discipline’s damage type unless stated otherwise, and Advanced Training riders use the type specified in their text. The Holdout Option is useful against damage immunity, not Resistance. Psychokinesis already deals force damage and gains no benefit from it.**

> **Design Note — Attack Bonus:** Psionic Focus mirrors the expected accuracy progression of magic weapons without making Manifested Strike an item.
>
> **Design Note — Melee Pressure: Manifested Strike follows the normal disadvantage rule for ranged attacks made while threatened. Because Psi and Blood Tax are committed before the roll, Overloading from a bad position is especially risky. Reposition rather than treating the subclass as a melee striker.**

**Overload** · *3rd Level · On Declaration*

Declare that you are Overloading a rider or standalone feature when you declare that feature — for a rider, before the Manifested Strike attack roll. Manifested Strike itself can never be Overloaded and never generates Blood Tax. See Overload Tier System (Section 01) for full rules.

**Signature Rider** · *3rd Level · Passive*

Your Discipline’s 3rd-level rider costs 0 Psi on every use, at every tier. You can apply it to any number of your Manifested Strike hits, subject to the normal limit of one rider per hit. You can Overload it normally without spending Psi, but you still pay its Blood Tax on declaration. Only one rider in each Attack action can be Overloaded to Tier 2. The four Signature Riders are Ember Bolt, Glacial Spike, Telekinetic Shove, and Static Discharge.

**Kinetic Mastery** · *3rd Level · Passive*

Your Manifested Strike has a mastery property determined by your Discipline. You can use that property, and it does not count against the number of weapons you can have mastery with from your Weapon Mastery feature.

**Tactical Master:** Beginning at Fighter level 9, when you make a Manifested Strike, you can use Tactical Master to replace its Kinetic Mastery property with Push, Sap, or Slow for that attack. The chosen property replaces Kinetic Mastery for that attack rather than stacking with it.

**Pyrokinesis — Graze:** If your Manifested Strike attack roll misses, the target still takes damage equal to your Psionic Ability modifier, of your Manifested Strike’s damage type.

**Cryokinesis — Slow:** If you hit a creature and deal damage to it, you can reduce its Speed by 10 feet until the start of your next turn.

**Psychokinesis — Push:** If you hit a creature that is Large or smaller, you can push it up to 10 feet straight away from you. If you also apply Telekinetic Shove on that hit, Telekinetic Shove replaces this movement (you move the target once, not twice).

**Electrokinesis — Sap:** If you hit a creature, it has disadvantage on its next attack roll before the start of your next turn.

**Graze and the Holdout Option:** Graze deals Manifested Strike damage, so it follows the strike. If you declare the Holdout Option, Graze deals force damage equal to half your Psionic Ability modifier (rounded down), exactly as the strike itself is halved.

**Masteries coexist with your riders. Slow adds to Glacial Spike. On a hit where you apply Telekinetic Shove, Shove replaces the Push mastery’s movement — you move the target once, using Shove’s direction and distance. The replacement happens when you declare Shove, not when it lands, so a successful save leaves you with neither movement. Your mastery remains free and automatic; a Signature Rider also costs no Psi but occupies the hit’s one rider slot.**

**Slow + Glacial Spike timing:** Slow and Glacial Spike are separate Speed reductions and stack with each other. A target affected by both is reduced by 20 feet until the start of your next turn; when Slow expires, Glacial Spike’s remaining 10-foot reduction continues until the end of that turn. Neither effect stacks with additional applications of itself.

**Masteries and Damage Immunity: Sap and Push trigger on a hit, so damage immunity does not prevent them. Graze and Slow require damage; against an immune creature, they work only if the Holdout Option allows the strike to deal force damage.**

**Empathic Sense** · *7th Level · Passive / ½PB Uses · Short/Long Rest*

Passive: Your passive Insight (Wisdom) score increases by your Psionic Ability modifier. (If your table does not track a passive Insight score, treat it as 10 + your Wisdom modifier + your Proficiency Bonus if proficient, then add your Psionic Ability modifier from this feature.) Active Scan: As a bonus action, you project a momentary telepathic pulse. At the instant you activate it, you sense the number and direction of creatures within range that harbor hostile intent toward you or a creature you regard as an ally, provided each has a discernible mind and emotions you can read. The scan is instantaneous and does not update if a creature moves, enters or leaves the range, or its intent changes. It does not reveal identity, exact location, thoughts, motive, or intended action. This is a standalone feature; Blood Tax applies on activation if Overloaded. You can use the scan a number of times equal to half your Proficiency Bonus (rounded down), regaining all expended uses on a short or long rest. T0: 15-foot range. Tier 1 Overload: Range increases to 30 feet. Tier 2 Overload: Range increases to 60 feet.

**Vanguard Training** · *7th Level · Passive*

You gain proficiency in one of the following skills of your choice: Arcana, Insight, Intimidation, Investigation, Perception, or Persuasion. You also add your Psionic Ability modifier to checks using that skill.

**Advanced Training I: Deflection Screen** · *5th Level · 1 Psi · Reaction*

Your psionic instincts develop a reflexive shield. When you take damage, you may use your reaction and spend 1 Psi to reduce it by 3d8 + your Psionic Ability modifier. Deflection Screen can reduce only damage from a source other than yourself; it cannot reduce Blood Tax or any other damage this subclass inflicts on you.

**Advanced Training II: Phase Step** · *10th Level · 1 Psi · Bonus Action*

Your psionic control extends to spatial displacement. Teleport up to 15 feet to an unoccupied space you can see. This movement does not provoke opportunity attacks.

**Advanced Training III** · *15th Level · Passive*

Your psionic mastery deepens. Choose one feature from the Advanced Training pool (Section 05).

**Swapping:** You may replace your chosen feature whenever you gain a Fighter level. There is no Psi cost to swap.

**Advanced Training IV** · *18th Level · Passive*

Choose a second feature from the Advanced Training pool (Section 05). You cannot choose the same feature twice.

**Swapping:** You may replace your chosen feature whenever you gain a Fighter level. There is no Psi cost to swap.

*At 18th level a Vanguard holds two Advanced Training picks (2 of 8). At 20th a third pick is added, bringing the total to 3 of 8 alongside Deflection Screen, Phase Step, and the full five-feature discipline progression.*

**Psionic Apex** · *18th Level · Passive*

Your psionic mastery reaches its zenith. You gain the following benefit:

**Overload Mastery:** Once per Short or Long Rest, when you declare your first Overload of a turn, you can activate this feature before paying Blood Tax. Until the end of that turn, including during any additional Attack action from Action Surge, halve the Blood Tax you pay after applying Resistance or any other reduction, rounding down. Overload Mastery can reduce Blood Tax below its normal minimum, but never below 1 damage for an individual Overload.

**Advanced Training V** · *20th Level · Passive*

Choose a third feature from the Advanced Training pool (Section 05). You cannot choose the same feature more than once.

**Swapping:** You may replace your chosen feature whenever you gain a Fighter level. There is no Psi cost to swap.

# 03 SUBCLASS FEATURE TABLE

| Level | Feature                                                                                                                                                           |
|-------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 3rd   | Psionic Discipline, Discipline Signature Save, Psi Reservoir, Psionic Link, Manifested Strike, Overload, Signature Rider, Kinetic Mastery, Discipline 3rd Feature |
| 5th   | Advanced Training I: Deflection Screen                                                                                                                            |
| 7th   | Empathic Sense, Vanguard Training, Discipline 7th Feature                                                                                                         |
| 10th  | Discipline 10th Feature, Advanced Training II (Phase Step), Tier 2 Overload                                                                                       |
| 15th  | Discipline 15th Feature, Advanced Training III (1 high-tier pick)                                                                                                 |
| 18th  | Advanced Training IV (1 high-tier pick), Psionic Apex                                                                                                             |
| 20th  | Discipline 20th Feature, Advanced Training V (pool pick)                                                                                                          |

**Psi Cost Reference**

| Level | Feature             | Discipline            | Psi        | Type                            |
|-------|---------------------|-----------------------|------------|---------------------------------|
| 3rd   | Glacial Spike       | *Cryokinesis*         | 0          | Rider                           |
| 3rd   | Ember Bolt          | *Pyrokinesis*         | 0          | Rider                           |
| 3rd   | Telekinetic Shove   | *Psychokinesis*       | 0          | Rider                           |
| 3rd   | Static Discharge    | *Electrokinesis*      | 0          | Rider                           |
| 5th   | Deflection Screen   | *Universal (AT I)*    | **1**      | Reaction                        |
| 7th   | Empathic Sense      | *Universal*           | **0**      | Bonus Action · Limited Uses     |
| 7th   | Snow Chains         | *Cryokinesis*         | **2**      | Rider (1×/action)               |
| 7th   | Thermal Fracture    | *Pyrokinesis*         | 1          | Rider (1×/action)               |
| 7th   | Vectored Thrust     | *Psychokinesis*       | **2**      | Bonus Action · Conc             |
| 7th   | Branching Bolt      | *Electrokinesis*      | 2          | Rider (1×/action)               |
| 10th  | Frozen Ground       | *Cryokinesis*         | **2**      | Action · Concentration          |
| 10th  | Cinder Lance        | *Pyrokinesis*         | 3          | Rider (1×/action)               |
| 10th  | Explosion/Implosion | *Psychokinesis*       | **2**      | Rider (1×/action)               |
| 10th  | Electron Burst      | *Electrokinesis*      | **2**      | Rider (1×/action)               |
| 10th  | Phase Step          | *Universal (AT II)*   | **1**      | Bonus Action                    |
| 15th  | Arctic Tempest      | *Cryokinesis*         | **3**      | Action                          |
| 15th  | Flare               | *Pyrokinesis*         | 3          | Rider (1×/action)               |
| 15th  | Telekinetic Slam    | *Psychokinesis*       | **3**      | Action                          |
| 15th  | Forked Lightning    | *Electrokinesis*      | 3          | Action                          |
| 15th  | AT III pick         | *Universal*           | **Varies** | Varies                          |
| 18th  | AT IV pick          | *Universal*           | **Varies** | Varies                          |
| 20th  | AT V pick           | *Universal*           | **Varies** | Varies                          |
| 15th+ | Mind Shred          | *Universal (AT pool)* | 3          | Rider (1×/action)               |
| 15th+ | Beguile             | *Universal (AT pool)* | **3**      | Action · Concentration          |
| 15th+ | Mind Lock           | *Universal (AT pool)* | 3          | Rider (1×/action)               |
| 15th+ | Gravitic Press      | *Universal (AT pool)* | **3**      | Action · Concentration          |
| 15th+ | Barrier             | *Universal (AT pool)* | **3**      | Bonus Action                    |
| 15th+ | Improved Phase Step | *Universal (AT pool)* | **3**      | Bonus Action                    |
| 18th+ | Overload Mastery II | *Universal (AT pool)* | **0**      | Passive · Requires Psionic Apex |
| 15th+ | Inner Reserve       | *Universal (AT pool)* | **0**      | Passive                         |
| 20th  | Absolute Zero       | *Cryokinesis*         | **5**      | Action                          |
| 20th  | Furnace Strike      | *Pyrokinesis*         | 5          | Rider (1×/action)               |
| 20th  | Mass Levitation     | *Psychokinesis*       | **5**      | Action · Concentration          |
| 20th  | Ball Lightning      | *Electrokinesis*      | **5**      | Action · Concentration          |

# 04 DISCIPLINES

Choose one Discipline at 3rd level. Your Discipline changes your Manifested Strike’s damage type and grants features at 3rd, 7th, 10th, 15th, and 20th level.

## Discipline I — CRYOKINESIS \[ Escalating Lockdown \] · Cold damage

*A control discipline that builds pressure methodically — speed reduction becomes restraint becomes stun, tightening the vice each round until nothing moves.*

**Glacial Spike** · *3rd · 0 Psi · On Manifested Strike Hit*

**T0:** The target takes 2 cold damage on hit (fixed, does not scale), and its Speed is reduced by 10 feet until the end of your next turn. This reduction does not stack with itself.

**Tier 1 Overload:** The target must make a Constitution saving throw. On a failed save, its Speed becomes 0 until the end of your next turn instead. On a successful save, the Tier 0 Speed reduction remains.

**Tier 2 Overload:** On a failed save, the target is Restrained until the end of your next turn instead of having its Speed become 0. On a successful save, the Tier 0 Speed reduction remains.

**Snow Chains** · *7th · 2 Psi · On Manifested Strike Hit · Once per Attack Action*

**T0:** The target’s speed becomes 0 until the end of your next turn (no save). The target must then make a Con save; on a failure, it is also Restrained until the end of your next turn.

**Tier 1 Overload:** On a failed save, the target also cannot take reactions until the start of your next turn.

**Tier 2 Overload:** On a failed save, the target is Stunned instead of Restrained until the end of your next turn.

**Frozen Ground** · *10th · 2 Psi · Action · Concentration, up to 1 minute*

**T0: Create a 15-ft-radius, 20-ft-high Cylinder of icy difficult terrain centered on a point within 60 ft. When a creature enters the Cylinder for the first time on a turn or starts its turn there, it must make a Con save. On a failed save, its Speed becomes 0 until the end of the current turn.**

**Tier 1 Overload:** Expand the radius to 25 ft.

**Tier 2 Overload: On a failed save, the target is Restrained until the end of your next turn instead.**

**Ribbon:** While Frozen Ground is active, you ignore difficult terrain created by your own ice.

**Arctic Tempest** · *15th · 3 Psi · Action*

**T0:** Up to 3 creatures within 60 ft take 8d10 cold damage (Con save for half) and are Restrained until the end of your next turn on a failed save.

**Tier 1 Overload:** +2d10 damage.

**Tier 2 Overload: Damage increases to 12d10. On a failed save, targets become Stunned until the end of your next turn instead of Restrained.**

**Absolute Zero** · *20th · 5 Psi · Action*

**T0:** Choose one creature within 60 ft. The target must make a Constitution saving throw, taking 10d10 cold damage on a failed save, or half on a successful one. On a failed save, the target’s speed becomes 0 until the end of your next turn.

**Tier 1 Overload:** Damage increases to 12d10. On a failed save, the target is also Restrained until the end of your next turn.

**Tier 2 Overload: Damage increases to 14d10. On a failed save, the target is Stunned until the end of your next turn instead of Restrained. The target’s speed becomes 0 even on a successful save.**

## Discipline II — PYROKINESIS \[ Immediate Single-Target Damage \] · Fire damage

An immediate single-target damage discipline. Ember Bolt supplies repeatable pressure, Thermal Fracture opens a focus-fire window, and the upper ladder converts Psi into progressively larger on-hit bursts.

**Ember Bolt** · *3rd · 0 Psi · On Manifested Strike Hit*

**T0:** The target takes an additional 2 fire damage on hit. This bonus is fixed and there is no per-Attack-action cap.

**Tier 1 Overload:** The additional fire damage increases to 4.

**Tier 2 Overload:** The additional fire damage increases to 6.

**Thermal Fracture** · *7th · 1 Psi · On Manifested Strike Hit · Once per Attack Action*

**T0:** After the triggering hit resolves, the target’s AC is reduced by 1 until the start of your next turn. Thermal Fracture deals no added damage.

**Tier 1 Overload:** The AC reduction increases to 2.

**Tier 2 Overload:** The AC reduction increases to 3. Thermal Fracture does not stack; use the stronger reduction, or refresh an equal reduction. The triggering hit does not benefit, but subsequent attacks by you or your allies do.

**Cinder Lance** · *10th · 3 Psi · On Manifested Strike Hit · Once per Attack Action*

**T0:** The target takes additional fire damage equal to 2 Manifested Strike dice, always using the base die for your Fighter level.

**Tier 1 Overload:** The additional damage increases to 3 Manifested Strike dice.

**Tier 2 Overload:** The additional damage increases to 4 Manifested Strike dice, and this added damage ignores Resistance to fire damage.

**Flare** · *15th · 3 Psi · On Manifested Strike Hit · Once per Attack Action*

**T0:** The target takes an additional 3d10 fire damage and must make a Dexterity saving throw or be Blinded until the end of your next turn.

**Tier 1 Overload:** The additional damage increases to 4d10, and the target is Blinded until the end of your next turn with no saving throw.

**Tier 2 Overload:** The additional damage increases to 5d10. The target is Blinded with no saving throw, and the added damage ignores Resistance to fire damage.

**Furnace Strike** · *20th · 5 Psi · On Manifested Strike Hit · Once per Attack Action*

**T0:** The target takes an additional 5d10 fire damage.

**Tier 1 Overload:** The additional damage increases to 7d10.

**Tier 2 Overload:** The additional damage increases to 9d10, and this added damage ignores Resistance to fire damage.

Furnace Strike has no saving throw, condition, area, persistent effect, mark, or kill trigger. It is immediate focused damage attached to a Manifested Strike hit.

## Discipline III — PSYCHOKINESIS \[ Tactical Space Control \] · Force damage

*A repositioning specialist that dictates where enemies stand — controlling entry points, collapsing formations, and punishing poor positioning. Force is the least-resisted damage type in the game, and every inch of displacement is leverage. Forced movement from this subclass follows normal 5e rules unless a feature says otherwise.*

**Telekinetic Shove** · *3rd · 0 Psi · On Manifested Strike Hit*

**T0: When a Manifested Strike hits, the target takes 2 force damage, then makes a Strength saving throw. On a failed save, push it 10 feet in any horizontal direction. Applying Telekinetic Shove replaces Push mastery for that hit, whether the save succeeds or fails; the target is moved only once, and a successful save leaves it unmoved.**

**Tier 1 Overload:** The push distance increases to 15 ft on this hit.

**Tier 2 Overload:** The push distance increases to 20 ft, and on a failed save the target’s Speed becomes 0 until the end of your next turn.

**Vectored Thrust** · *7th · 2 Psi · Bonus Action · Concentration, up to 10 minutes*

**T0:** You gain a fly speed of 30 feet for the duration. The effect ends early if you are incapacitated.

**Vectored Thrust is a standalone Bonus Action; Blood Tax is paid when it is activated.**

**Tier 1 Overload:** Flying does not provoke opportunity attacks.

**Tier 2 Overload:** Your fly speed increases by 5 × your Proficiency Bonus in feet.

**Explosion/Implosion** · *10th · 2 Psi · On Manifested Strike Hit · Once per Attack Action*

**T0:** Release a telekinetic shockwave in a 15-ft-radius Sphere centered on the target. You choose Explosion (outward) or Implosion (inward) when you activate. Each creature in the Sphere, including the struck target, must make a Strength saving throw. On a failed save, a creature is Restrained until the end of your next turn; each creature other than the struck target that fails is also pushed 15 ft away from or pulled 15 ft toward the target, matching your choice. The struck target is never moved by this effect. Because the struck target is the Sphere's center, it has no inward or outward line of movement; that movement is geometrically impossible under Rider Target Parity, not an exception to its saving throw, Restrained condition, or Tier 2 damage. On a successful save, a creature is neither moved nor Restrained. Creatures cannot be moved into occupied spaces. Resolve the creatures’ movement in an order you choose. A creature whose path is fully blocked stops in the nearest unoccupied space along its line of movement.

**Tier 1 Overload:** The Sphere’s radius increases to 20 ft, and the push or pull distance increases to 30 ft.

**Tier 2 Overload:** Creatures that fail the save also take force damage equal to your Psionic Ability modifier from the impact.

*Use Telekinetic Shove on another hit to position the primary target, then Explosion to scatter a cluster or Implosion to collapse it inward.*

**Telekinetic Slam** · *15th · 3 Psi · Action*

*You seize a foe with overwhelming telekinetic force and slam it violently into the ground with crushing power.*

**T0:** Choose one creature you can see within 60 feet. The target must make a Strength saving throw, taking 8d10 force damage on a failed save, or half as much on a successful one. On a failed save, the target is also pushed 10 ft in any horizontal direction you choose.

**Tier 1 Overload:** The damage increases to 10d10. On a failed save, the push distance increases to 20 ft.

**Tier 2 Overload: The damage increases to 12d10. On a failed save, the push distance increases to 30 ft, provided the target travels along an unobstructed path to an unoccupied space you can see, and its Speed becomes 0 until the end of your next turn. On a successful save, the target is still pushed up to 10 ft in a horizontal direction of your choice.**

**Mass Levitation** · *20th · 5 Psi · Action · Concentration, up to 1 minute*

**T0:** Choose up to five Medium or smaller creatures within 60 ft, or up to two Large creatures. Huge or larger creatures are immune. Each target must make a Str save or be lifted 30 ft into the air and Restrained (hovering). At the start of each affected creature’s turn, it must repeat the Str save; on a success, it descends safely and the effect ends for that creature. While concentration is maintained, creatures that remain Restrained continue to hover. If concentration ends, all affected creatures fall.


**Tier 1 Overload:** Levitated creatures have disadvantage on the repeat Str save against this feature. At the start of each of your turns, you may move each creature still levitated by this feature up to 15 ft in any direction to an unoccupied space you can see. This is forced movement; the creature remains lifted and Restrained throughout.

**Tier 2 Overload:** At the start of each levitated creature’s turn, it first repeats the Strength saving throw from T0. On a success, it descends safely and takes no damage from this tier. On a failure, it remains levitated and takes force damage equal to 2× your Psionic Ability modifier.

## Discipline IV — ELECTROKINESIS \[ Arcing Disruption \] · Lightning damage

A spreading-damage discipline built to punish clustered enemies. Static Discharge splashes adjacent creatures, Branching Bolt reaches selected secondaries, Electron Burst bursts a knot of foes, and Forked Lightning clears the room.

**Static Discharge** · *3rd · 0 Psi · On Manifested Strike Hit*

**T0:** The struck target and up to one other creature of your choice within 5 feet of it each take 2 lightning damage, with no saving throw.

**Tier 1 Overload:** You can instead affect the struck target and up to a number of other creatures equal to your Proficiency Bonus within 5 feet of it. Each affected creature takes 2 lightning damage.

**Tier 2 Overload:** Retains the Tier 1 targets and damage. Each affected creature must make a Charisma saving throw or be unable to take reactions until the start of your next turn. This save applies even if the creature takes no lightning damage because of immunity.

**Branching Bolt** · *7th · 2 Psi · On Manifested Strike Hit · Once per Attack Action*

When you declare this rider, choose up to the tier's maximum number of additional creatures. You may choose no additional creature; any unused branches are forfeited. The struck creature is always included.

**T0:** The struck target and up to one other creature of your choice within 15 feet of it each take lightning damage equal to 1 Manifested Strike die, with no saving throw.

**Tier 1 Overload:** You can instead affect the struck target and up to two other creatures within 15 feet of it.

**Tier 2 Overload:** You can instead affect the struck target and up to three other creatures within 15 feet of it. Each additional creature can be selected only once, and the current does not arc onward.

**Electron Burst** · *10th · 2 Psi · On Manifested Strike Hit · Once per Attack Action*

**T0:** Lightning bursts outward in a 10-ft-radius Sphere centered on the struck target. The burst occurs even if no creature other than the struck target is in the Sphere. Each creature in the area, including the struck target, must make a Charisma saving throw, taking 2d8 lightning damage on a failed save, or half as much on a successful one.

**Tier 1 Overload:** The damage increases to 3d8. The radius remains 10 feet.

**Tier 2 Overload:** The damage increases to 4d8. A creature that fails the save also cannot take reactions and has disadvantage on attack rolls until the start of your next turn.

**Forked Lightning** · *15th · 3 Psi · Action*

**T0:** Choose one creature you can see within 60 feet as the primary target. It takes 8d8 lightning damage (Charisma save for half). The lightning then arcs to up to 3 other creatures within 30 feet of the primary target; each takes 4d8 lightning damage (Charisma save for half).

**Tier 1 Overload:** The primary target takes 10d8, and the lightning arcs to up to 4 other creatures, each taking 5d8.

**Tier 2 Overload:** The primary target takes 12d8, and the lightning arcs to up to 5 other creatures, each taking 6d8. Every target that fails its save cannot take reactions and has disadvantage on attack rolls until the start of your next turn. If the primary target fails, its Speed also becomes 0 for that duration.

**Ball Lightning** · *20th · 5 Psi · Action · Concentration, up to 1 minute*

**T0:** Conjure a hovering orb of lightning filling a 15-ft-radius Sphere at a point within 60 feet. When a creature enters the Sphere for the first time on a turn or starts its turn there, it must make a Charisma saving throw, taking 4d8 lightning damage on a failed save, or half as much on a successful one. As a bonus action on your turn, you can move the orb up to 15 feet.

**Tier 1 Overload:** The radius increases to 30 feet.

**Tier 2 Overload:** The Sphere retains the Tier 1 radius. A creature that fails its save cannot take reactions and has disadvantage on attack rolls while inside it. These effects end immediately when the creature leaves.

Ball Lightning is a standalone Action requiring Concentration, not a rider. Moving the orb onto a creature does not trigger damage immediately; the creature triggers when it enters on its own turn or starts its turn inside.

# 05 ADVANCED TRAINING

> These are universal psionic techniques, not tied to any Discipline. Advanced Training III (15th) grants one pick, Advanced Training IV (18th) grants a second, and Advanced Training V (20th) grants a third, for three of eight at 20th level. You may swap a pick whenever you gain a Fighter level. Deflection Screen and Phase Step are core features granted at 5th and 10th level; their Overload tiers are listed here for reference.

**ADVANCED TRAINING I AND II: DEFLECTION SCREEN AND PHASE STEP**

**Advanced Training I: Deflection Screen** · *5th Level · 1 Psi · Reaction*

**T0:** When you take damage, you may use your reaction and spend 1 Psi to reduce it by 3d8 + your Psionic Ability modifier. Not usable against Blood Tax or self-inflicted damage.

**Tier 1 Overload: The reduction increases to 5d8 + your Psionic Ability modifier.**

**Tier 2 Overload: The reduction increases to 7d8 + your Psionic Ability modifier. The attacker must make a Strength saving throw. On a failed save, it is pushed up to 15 feet away from you and knocked Prone. On a successful save, it is pushed 5 feet away. If the damage had no originating creature (a trap, environmental effect, falling damage, or similar), this push-and-Prone effect does not occur; the damage reduction still applies.**

**Advanced Training II: Phase Step** · *10th Level · 1 Psi · Bonus Action*

**T0:** Teleport up to 15 ft to an unoccupied space you can see. This movement does not provoke opportunity attacks.

**Tier 1 Overload:** Teleport up to 30 ft instead.

**Tier 2 Overload: As Tier 1. Choose either the space you left or the space where you appear. Each creature of your choice within 5 feet of that space must make your Discipline's signature saving throw against your Psionic save DC. On a failed save, it cannot take reactions until the start of your next turn.**

**ADVANCED TRAINING III, IV, AND V (15TH, 18TH, AND 20TH LEVEL)**

**Mind Shred** · *High Tier · 3 Psi · On Manifested Strike Hit · Once per Attack Action*

**T0:** The target takes 2d8 psychic damage. There is no saving throw.

**Tier 1 Overload:** Damage increases to 3d8 psychic.

**Tier 2 Overload:** Damage increases to 4d8 psychic, and this damage ignores Resistance to psychic damage.

**Beguile** · *High Tier · 3 Psi · Action*

**T0:** You produce the effects of charm person (Concentration, up to 1 hour) without casting a spell. The target makes a Charisma saving throw against your Psionic save DC. This feature is exclusive — you choose one tier when you activate it. Higher tiers replace the effect entirely; they do not stack.

**Tier 1 Overload:** You instead produce the effects of suggestion (Concentration, up to 8 hours) without casting a spell. Charisma save against your Psionic save DC.

**Tier 2 Overload:** You instead produce the effects of mass suggestion, affecting up to five creatures you can see within 60 feet (Concentration, up to 8 hours), without casting a spell. Each target makes a Charisma saving throw against your Psionic save DC.

*Beguile is a standalone Action — it does not require a Manifested Strike hit and is not a rider. All tiers require Concentration and consume your concentration slot. Beguile is not a spell: it requires no components, cannot be Counterspelled or dispelled, is unaffected by features that key off spellcasting (for example, a feature that triggers specifically from casting a spell), and its save is always Charisma regardless of your Discipline. It is escalating mental influence, not spellcasting.*

**Mind Lock** · *High Tier · 3 Psi · On Manifested Strike Hit · Once per Attack Action*

**T0:** The target is Blinded until the end of your next turn. There is no saving throw.

**Tier 1 Overload:** The target is Blinded as at Tier 0 and must make an Intelligence saving throw. On a failed save it is also Incapacitated until the end of your next turn.

**Tier 2 Overload:** The target is Blinded as at Tier 0 and must make an Intelligence saving throw. On a failed save it is Stunned until the end of your next turn instead of Incapacitated.

Mind Lock is the Advanced Training pool’s dedicated control pick. Blinded is its reliable floor; Incapacitated and Stunned are the Overload payoff. Mind Shred is the damage choice, while Mind Lock is the control choice.

**Gravitic Press** · *High Tier · 3 Psi · Action · Concentration, up to 1 minute*

**T0:** Create a 15-ft-radius, 20-ft-high Cylinder of intensified gravity centered on a point within 60 ft. The area is difficult terrain for the duration. Any creature in the zone has its speed halved (no save). A flying creature that enters the zone or starts its turn there immediately falls to the ground, taking fall damage as normal, and cannot fly or gain a fly speed while it remains in the zone. A creature that enters the area for the first time on a turn or starts its turn there must make a Strength saving throw or be unable to take reactions until the start of its next turn.

**Tier 1 Overload:** Creatures in the Cylinder have disadvantage on attack rolls.

**Tier 2 Overload:** A creature that fails the saving throw also has its Speed reduced to 0 until the start of its next turn.

*Gravitic Press is a standalone Action — it does not require a Manifested Strike hit and is not a rider. Requires Concentration.*

**Barrier** · *High Tier · 3 Psi · Bonus Action*

**T0:** For 1 minute, choose one of the following effects, which lasts for the duration. Blade Shield: you have resistance to bludgeoning, piercing, and slashing damage from weapon attacks. Elemental Shroud: choose one damage type from acid, cold, fire, lightning, or thunder; you have resistance to that damage type. Spellward: you have advantage on saving throws against spells. Steadfast Guard: you have advantage on Strength saving throws, and on ability checks and saving throws to resist being grappled, shoved, knocked prone, or forcibly moved. Mental Bulwark: you have advantage on saving throws against being charmed, frightened, blinded, restrained, incapacitated, paralyzed, or stunned.

**Tier 1 Overload:** Choose two of the five effects instead of one.

**Tier 2 Overload:** The duration increases to 10 minutes. While Barrier is active and you are not in Initiative, you may spend 1 Psi to replace one of your chosen effects with another effect from the list. If Elemental Shroud is active, you may instead change its chosen damage type. You cannot choose an effect you already have active.

*Barrier is a standalone Bonus Action — not a rider.*

**Improved Phase Step** · *High Tier · 3 Psi · Bonus Action*

**T0: As a bonus action, teleport up to 30 feet to an unoccupied space you can see. Choose either the space you left or the space where you appear as the origin of a 5-foot-radius Sphere. Choose up to three other creatures in the Sphere. Each chosen creature must make your Discipline’s signature saving throw against your Psionic save DC, taking 2d10 damage of your Manifested Strike’s damage type on a failed save, or half as much on a successful one. This movement does not provoke opportunity attacks, and you are unaffected by the burst.**

**Tier 1 Overload:** The teleport range increases to 60 feet and the burst damage increases to 3d10.

**Tier 2 Overload: The burst damage increases to 4d10. A creature that fails the save also cannot take reactions until the start of your next turn.**

*Improved Phase Step is a standalone Bonus Action — it is not a rider and does not require a Manifested Strike hit. Where Phase Step is a cheap utility blink, Improved Phase Step is the longer, costlier blink that detonates on either end of the jump.*

**Overload Mastery II** · *High Tier · Passive · Requires Psionic Apex (18th)*

You can choose this feature only if you have Psionic Apex. You gain one additional use of Overload Mastery per Short or Long Rest. This stacks with the use granted by Psionic Apex, giving you two total uses per Short or Long Rest.

**Inner Reserve** · *High Tier · Passive*

Your maximum Psi point pool increases by 4. You cannot choose this feature more than once.

# 06 DESIGN IDENTITY

> **Complexity: Advanced** — Manages Psi Points, Overload tiers, and concentration. Recommended for players comfortable with resource management. New to this style of play? Start with the SRD Champion before taking on this higher-complexity subclass.
>
> Mental-stat Fighter · Martial controller with discipline-specific damage — Voluntary self-destructive nova engine · Blood Tax scales with Proficiency Bonus — Four Discipline identities · Universal psionic toolkit · No Psi recovery in combat

# 07 DISCIPLINE CHEATSHEETS

*Quick-reference feature list per Discipline. Detailed play patterns and sample turns are available in the separate Discipline Player Sheets (not included in this document).*

**CRYOKINESIS — ESCALATING LOCKDOWN**

3rd: Glacial Spike (rider, unlimited). 7th: Snow Chains (rider, once/Attack action). 10th: Frozen Ground (action, concentration). 15th: Arctic Tempest (action, nova). 20th: Absolute Zero (single-target nuke, 10d10 cold). Identity: speed → 0 → Restrained → Stunned. No innate flight; use Phase Step.

**PYROKINESIS — IMMEDIATE SINGLE-TARGET DAMAGE**

3rd: Ember Bolt (rider, unlimited). 7th: Thermal Fracture (rider, once/Attack action, AC −1/−2/−3). 10th: Cinder Lance (rider, once/Attack action, +2/+3/+4 MS dice). 15th: Flare (rider, once/Attack action, 3d10/4d10/5d10 and Blind). 20th: Furnace Strike (rider, once/Attack action, 5d10/7d10/9d10). Identity: immediate single-target damage with one coordinated armor-break option.

**PSYCHOKINESIS — TACTICAL SPACE CONTROL**

3rd: Telekinetic Shove (rider, unlimited). 7th: Vectored Thrust (bonus action, concentration, flight). 10th: Explosion/Implosion (rider, once/Attack action, push or pull). 15th: Telekinetic Slam (action, single-target nuke). 20th: Mass Levitation (5 Psi, action, concentration, up to 5 targets Restrained). Identity: push, pull, pin, fly. Force is least-resisted. Innate flight via VT.

**ELECTROKINESIS — ARCING DISRUPTION**

3rd: Static Discharge (rider, struck target plus up to 1/PB/PB additional nearby creatures for 2 damage each; T2 reaction denial). 7th: Branching Bolt (rider, once/Attack action, struck target plus up to 1/2/3 additional creatures for 1 MS die each; unused branches may be forfeited). 10th: Electron Burst (rider, once/Attack action, 10-ft burst including the struck target for 2d8/3d8/4d8; no additional creature is required). 15th: Forked Lightning (action, primary plus 3/4/5 secondaries). 20th: Ball Lightning (5 Psi, action, concentration, movable 15/30-ft orb). Identity: spreading damage and room clearing. Charisma signature save. Soft spot: lightning immunity.

**Universal tools (all disciplines):** Deflection Screen (5th, 3d8/5d8/7d8+mod soak). Phase Step (10th, teleport 15 ft). AT III (15th, 1 of 8 picks). AT IV + Psionic Apex (18th, 2nd pick + Overload Mastery). AT V (20th, 3rd pick). 20th: Discipline capstone + AT V.

# LICENSE AND SRD ATTRIBUTION

Original Kinetic Vanguard material is released under the project’s attribution terms: you may use, copy, modify, and redistribute the original homebrew material for non-commercial purposes with credit to **NixNinja**. Commercial use of the original Kinetic Vanguard material requires prior written permission.

SRD-derived rules text and references are separately governed by the Creative Commons Attribution 4.0 International License. The project’s original-material terms do not restrict rights granted by CC-BY-4.0. See `SRD_ATTRIBUTION.md` for the required attribution statement, exact pinned source, and checksum status.

© 2024–present NixNinja. Rights reserved in the original Kinetic Vanguard material except as granted above.
