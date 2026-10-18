from dataclasses import replace
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from harness.authority import AuthorityModel
from harness.damage_harness import Package, _kv_dpr_for_schedule, _raw_distribution, _rider_values, _rule_damage
from harness.model import load_config, load_targets

class SurgicalDamageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model=AuthorityModel.load()
        cls.target=replace(load_targets(levels={20})[0],damage_resistances=frozenset(),damage_immunities=frozenset(),damage_vulnerabilities=frozenset())

    def assertPairAlmostEqual(self,actual,expected):
        for value,reference in zip(actual,expected):self.assertAlmostEqual(value,reference)

    def rider(self,entity,tier=0,level=20,cluster=6,mode=None,target=None):
        rule=self.model.features[entity]
        return _rider_values(self.model,target or self.target,rule['discipline_ids'][0],cluster,level,6,5,12,Package(entity,tier,rule['psi_cost'],self.model.blood_tax(level,tier),mode))

    def test_absolute_zero_halves_the_entire_packet_with_defenses_after_rounding(self):
        for tier,flat in enumerate([45,55,65]):
            damage=self.model.features['absolute_zero']['damage_tiers'][tier]['damage']
            distribution=_raw_distribution(damage,12,5)
            self.assertEqual(min(distribution),6+flat);self.assertEqual(max(distribution),60+flat)
            self.assertAlmostEqual(sum(distribution.values()),1)
            self.assertAlmostEqual(_rule_damage(self.target,damage,'cold',12,5,0),33+flat)
            self.assertAlmostEqual(_rule_damage(self.target,damage,'cold',12,5,1),(33+flat)/2-.25)
            resistant=replace(self.target,damage_resistances=frozenset({'cold'}))
            expected=sum(p*(value//2//2) for value,p in distribution.items())
            self.assertAlmostEqual(_rule_damage(resistant,damage,'cold',12,5,1),expected)
            self.assertAlmostEqual(_rule_damage(resistant,damage,'cold',12,5,1,True),(33+flat)/2-.25)
            immune=replace(self.target,damage_immunities=frozenset({'cold'}))
            self.assertEqual(_rule_damage(immune,damage,'cold',12,5,0,True),0)

    def test_shove_increases_only_from_fighter_18_at_every_tier(self):
        for tier in range(3):
            for level,damage in [(17,2),(18,4),(20,4)]:self.assertPairAlmostEqual(self.rider('telekinetic_shove',tier,level),(damage,damage))

    def test_branching_requires_allocation_and_preserves_costs_from_grant(self):
        with self.assertRaisesRegex(ValueError,'allocation'):self.rider('branching_bolt')
        for level in [7,10,15,20]:
            for cluster in [1,2,3,6]:
                with patch('harness.damage_harness._KVDamagePlanner') as planner:
                    planner.return_value.solve.return_value=SimpleNamespace(primary=0,aggregate=0)
                    planner.return_value.selection.return_value=''
                    config=load_config()
                    if level==10:config['fighter_progression']['10']=dict(config['fighter_progression']['7'])
                    _kv_dpr_for_schedule(self.model,config,replace(self.target,level=level),'electrokinesis',cluster,(1,1,1))
                    packages=[p for p in planner.call_args.args[2] if p.entity_id=='branching_bolt']
                self.assertEqual({p.tier for p in packages},set() if cluster<3 else {0,1} if level==7 else {0,1,2})
                for package in packages:
                    self.assertIsNone(package.mode)
                    self.assertEqual(sum(package.allocation),package.tier+3)
                    self.assertLessEqual(len(package.allocation),cluster)
                    self.assertGreaterEqual(len(package.allocation),3)
                    self.assertEqual((package.psi,package.blood),(2,self.model.blood_tax(level,package.tier)))
                for tier in {p.tier for p in packages}:
                    self.assertTrue(any(p.tier==tier and p.allocation==(tier+1,1,1) for p in packages))
