"""Unknown service/template definitions are outside the accepted DS observation scope."""
import sys
import pytest
if not sys.platform.startswith("linux"):
    pytest.skip("Linux guest inventory",allow_module_level=True)
from e3_host import q2_journal_growth_guest as g

@pytest.mark.parametrize("manager",[None,1100])
def test_empty_declared_manager_never_enumerates_units_or_templates(manager):
    value=object.__new__(g.GuestInventory)
    value.description=dict(domain_units=[],expected_units=[])
    value.check=lambda:None
    value.ctl=lambda *a,**k:pytest.fail("No unknown unit, unit-file, template or empty query is allowed")
    assert value.startup_manager(user_uid=manager)==dict(scope="DECLARED_ONLY",domains=[],
        undeclared_unit_inventory="NOT_PERFORMED",indirect_startup="NOT_PERFORMED")

@pytest.mark.parametrize("user",[False,True])
def test_manager_queries_only_sorted_declared_domains(user):
    value=object.__new__(g.GuestInventory);value.check=lambda:None;calls=[]
    domains=[dict(name=n,manager="user" if user else "system",control_group="/"+n)
             for n in ("z.slice","a.slice")]
    value.description=dict(domain_units=domains+[dict(name="opposite.slice",manager="system" if user else "user",control_group="/opposite.slice")],expected_units=[dict(name="known.service")])
    def ctl(args,*,user_uid=None):
        calls.append((args,user_uid))
        assert args[0]=="show" and args[args.index("--")+1:]==["a.slice","z.slice"]
        assert user_uid==(1100 if user else None)
        blocks=[]
        for name in ("a.slice","z.slice"):
            row=dict.fromkeys(value.SHOW,"");row.update(Id=name,Names=name,LoadState="loaded",ControlGroup="/"+name)
            blocks.append("\n".join(k+"="+v for k,v in row.items()))
        return ("\n\n".join(blocks)+"\n").encode()
    value.ctl=ctl
    result=value.startup_manager(user_uid=1100 if user else None)
    assert [row['name'] for row in result['domains']]==['a.slice','z.slice']
    assert len(calls)==1 and result['scope']=='DECLARED_ONLY'
