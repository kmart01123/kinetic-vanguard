"""Independent checks for mandatory crowds and automatic allocated packets."""
import copy
import itertools
import math
import unittest
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from functools import lru_cache

from harness import damage_harness as d
from harness.authority import AuthorityModel
from harness.damage_allocation import allocations,validate_allocation
from harness.model import load_targets


def independent_allocations(budget,cluster,minimum=3):
    # Enumerate named targets directly, without the production composition helper.
    return {a for count in range(minimum,min(cluster,budget)+1) for a in itertools.product(range(1,budget+1),repeat=count) if sum(a)==budget}


def oracle_case(case):
    studied_enabled,prowess_enabled,apex_enabled=case
    model=AuthorityModel.load()
    target=replace(load_targets(levels={20})[0],ac=20,damage_resistances=frozenset(),damage_immunities=frozenset(),damage_vulnerabilities=frozenset())
    packages=[d.Package(None,0,0,0)]
    for tier,row in enumerate(model.features['branching_bolt']['damage_tiers']):
        packages.extend(d.Package('branching_bolt',tier,2,tier*6,allocation=a) for a in allocations(row['damage_allocation'],3))
    values={p:d._rider_values(model,target,'electrokinesis',3,20,6,5,12,p) for p in packages}
    planner=d._KVDamagePlanner(model,target,tuple(packages),values,(('normal',(0,11.5,18)),),((),()),11,2,(1,1),studied_enabled,prowess_enabled,4,24,model.projection['core']['overload']['mastery'],0,None,13.5 if apex_enabled else None)
    choices=[(None,(),0,0)]+[(tier,a,2,tier*6) for tier in range(3) for a in independent_allocations(tier+3,3)]
    def best(rows):return max(rows,key=lambda row:(row[1],row[0]))
    @lru_cache(None)
    def solve(turn,attacks,t2,studied,prowess,psi,blood,apex):
        if not attacks:
            return (0.,0.) if turn==1 else solve(turn+1,2,False,studied,prowess_enabled,psi,blood,apex_enabled)
        candidates=[]
        for tier,a,cost,tax in choices:
            if cost>psi or tax>blood or (tier==2 and t2):continue
            for declare_apex in ([False,True] if apex else [False]):
                total=[0.,0.]
                rolls=list(itertools.product(range(1,21),repeat=2)) if studied_enabled and studied else [(n,) for n in range(1,21)]
                for raw in rolls:
                    natural=max(raw);hit=natural==20 or (natural!=1 and natural+11>=20)
                    observed=[]
                    for convert in ([False,True] if not hit and prowess else [False]):
                        lands=hit or convert
                        base=(18 if natural==20 else 11.5)+(13.5 if declare_apex else 0) if lands else 0
                        primary=(a[0]*6.5 if a else 0) if lands else 0
                        aggregate=sum(a)*6.5 if lands else 0
                        later=solve(turn,attacks-1,t2 or tier==2,studied_enabled and not lands,prowess and not convert,psi-cost,blood-tax,apex and not declare_apex)
                        observed.append((base+primary+later[0],base+aggregate+later[1]))
                    result=best(observed)
                    for index in (0,1):total[index]+=result[index]/len(rolls)
                candidates.append(tuple(total))
        return best(candidates)
    actual=planner.solve();expected=solve(0,2,False,False,prowess_enabled,4,24,apex_enabled)
    assert math.isclose(actual.primary,expected[0],abs_tol=1e-8),(case,actual,expected)
    assert math.isclose(actual.aggregate,expected[1],abs_tol=1e-8),(case,actual,expected)
    assert 'extra_' not in planner.selection()
    planner.clear()
    return case


class DamageAllocationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model=AuthorityModel.load()
        cls.target=replace(load_targets(levels={20})[0],damage_resistances=frozenset(),damage_immunities=frozenset(),damage_vulnerabilities=frozenset())

    def test_all_legal_allocations_require_three_targets_at_every_tier(self):
        for tier,row in enumerate(self.model.features['branching_bolt']['damage_tiers']):
            for cluster in range(1,7):
                expected={(a[0],*sorted(a[1:])) for a in independent_allocations(tier+3,cluster)}
                self.assertEqual(set(allocations(row['damage_allocation'],cluster)),expected)

    def test_independent_multiturn_oracles_with_eight_workers(self):
        with ProcessPoolExecutor(max_workers=8) as pool:
            self.assertEqual(len(list(pool.map(oracle_case,itertools.product([False,True],repeat=3)))),8)

    def test_landed_packets_apply_defenses_once_per_target(self):
        for tier,row in enumerate(self.model.features['branching_bolt']['damage_tiers']):
            for a in independent_allocations(tier+3,6):
                for defense in ('normal','resistant','immune','vulnerable'):
                    target=replace(self.target,damage_resistances=frozenset({'lightning'}) if defense=='resistant' else frozenset(),damage_immunities=frozenset({'lightning'}) if defense=='immune' else frozenset(),damage_vulnerabilities=frozenset({'lightning'}) if defense=='vulnerable' else frozenset())
                    package=d.Package('branching_bolt',tier,2,tier*6,allocation=a)
                    actual=d._rider_values(self.model,target,'electrokinesis',6,20,6,5,12,package)
                    values=[0 if defense=='immune' else n*13 if defense=='vulnerable' else n*3.25-.25 if defense=='resistant' and tier<2 else n*6.5 for n in a]
                    self.assertAlmostEqual(actual[0],values[0]);self.assertAlmostEqual(actual[1],sum(values))

    def test_only_original_hit_controls_rider_and_critical_never_bonuses_it(self):
        for a in [(3,1,1),(1,3,1),(2,2,1),(1,1,1,1,1)]:
            package=d.Package('branching_bolt',2,2,12,allocation=a)
            values={package:d._rider_values(self.model,self.target,'electrokinesis',5,20,6,5,12,package)}
            planner=d._KVDamagePlanner(self.model,self.target,(package,),values,(('normal',(0,11.5,18)),),((),),11,1,(1,),True,True,2,12,self.model.projection['core']['overload']['mastery'],0,None,None)
            for outcome in ['miss','hit','critical']:
                options=planner._roll_options(0,0,outcome,False,True,0,False)
                for resolution,studied,apex,prowess,reduction,primary,aggregate in options:
                    if resolution=='miss':self.assertEqual((primary,aggregate),(0,0));self.assertTrue(studied)
                    else:
                        base=18 if resolution=='critical' else 11.5
                        self.assertAlmostEqual(primary,base+a[0]*6.5);self.assertAlmostEqual(aggregate,base+32.5)
                        self.assertFalse(studied)
                        self.assertEqual(prowess,resolution!='prowess')
            planner.clear()

    def test_neutral_minimum_and_budget_are_read_from_projection(self):
        projection=copy.deepcopy(self.model.projection)
        rule=next(row for row in projection['features'] if row['entity_id']=='branching_bolt');rule['entity_id']='synthetic_allocation'
        spec=rule['damage_tiers'][2]['damage_allocation'];spec['minimum_targets']=4
        self.assertEqual(allocations(spec,3),[])
        model=AuthorityModel(projection)
        package=d.Package('synthetic_allocation',2,2,12,allocation=(2,1,1,1))
        actual=d._rider_values(model,self.target,'electrokinesis',4,20,6,5,12,package)
        self.assertAlmostEqual(actual[0],13.);self.assertAlmostEqual(actual[1],32.5)
        spec['minimum_targets']=2
        self.assertIn((4,1),allocations(spec,2))

    def test_secondary_targets_must_all_be_hostile(self):
        spec=self.model.features['branching_bolt']['damage_tiers'][2]['damage_allocation']
        validate_allocation(spec,(3,1,1),secondary_hostile=(True,True))
        for hostile in [(False,False),(True,False),(False,True),(),(True,),(True,True,True),(1,True)]:
            with self.subTest(hostile=hostile),self.assertRaisesRegex(ValueError,"secondary target must be hostile"):
                validate_allocation(spec,(3,1,1),secondary_hostile=hostile)

    def test_invalid_allocations_and_old_attack_contract_fail_closed(self):
        spec=self.model.features['branching_bolt']['damage_tiers'][2]['damage_allocation']
        for a in [(),(5,),(4,1),(0,4,1),(-1,5,1),(1,1,1),(True,3,1),(1,1,1,1,1,1)]:
            with self.assertRaises(ValueError):validate_allocation(spec,a,secondary_hostile=(True,)*max(0,len(a)-1))
        for change in [{'secondary_target_eligibility':'any_creature'},{'dice_budget':6,'maximum_targets':6},{'minimum_targets':1},{'minimum_targets':6},{'minimum_targets':True},{'minimum_dice_per_target':0},{'packet':'per_die'},{'excess_attack':{}},{'retained_dice_per_target':2}]:
            with self.assertRaises(ValueError):allocations({**spec,**change},6)
        for a in [(3,1,1),(1,3,1)]:
            with self.assertRaises(ValueError):d._rider_values(self.model,self.target,'electrokinesis',2,20,6,5,12,d.Package('branching_bolt',2,2,12,allocation=a))

if __name__=='__main__':unittest.main()
