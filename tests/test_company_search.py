import pandas as pd
from research_engine import search_approved_devices,company_name_search

FRAME=pd.DataFrame([
 {'devicename':'Laser','address':'Meril Life Sciences Pvt. Ltd.','premises_add':'','role':'Manufacturer'},
 {'devicename':'Stent','address':'MERIL Healthcare','premises_add':'','role':'Manufacturer'},
 {'devicename':'Laser','address':'Other Laser Company','premises_add':'','role':'Manufacturer'},
 {'devicename':'Meril-branded catheter','address':'Unrelated Company','premises_add':'Meril warehouse','role':'Importer'},
 {'devicename':'Laser','address':None,'premises_add':'','role':'Manufacturer'},
])

def test_company_only_uses_manufacturer_not_prefilled_product_or_smart_synonyms():
    for smart in (True,False):
        result=search_approved_devices(FRAME,'Laser','meril','Company Name Only',ai_mode=smart)
        assert result.index.tolist()==[0,1]
        assert result.address.str.contains('meril',case=False,regex=False).all()

def test_manufacturer_is_also_required_in_other_scopes():
    for scope in ['Product Name Only','All Fields (Product, Brand, Models, Intended Use, License)']:
        result=search_approved_devices(FRAME,'Laser','Meril',scope)
        assert result.index.tolist()==[0]

def test_company_fallback_literal_punctuation_and_missing_columns():
    assert search_approved_devices(FRAME,'meril','','Company Name Only').index.tolist()==[0,1]
    assert company_name_search(FRAME,'Meril.*').empty
    assert company_name_search(FRAME.drop(columns='address'),'meril').empty
    assert search_approved_devices(FRAME,'Laser','','Product Name Only',ai_mode=False).index.tolist()==[0,2,4]

def test_role_filters_are_combined_with_company_and_product():
    import pandas as pd
    extra=pd.DataFrame([{'devicename':'Laser','address':'Meril India','role':' importer '},{'devicename':'Laser','address':'Other','role':'Importer'}])
    frame=pd.concat([FRAME,extra],ignore_index=True)
    assert search_approved_devices(frame,'Laser','meril','Company Name Only',role='Importer Only').index.tolist()==[5]
    assert search_approved_devices(frame,'Laser','meril','Product Name Only',role='Manufacturer Only').index.tolist()==[0]
    assert search_approved_devices(frame.drop(columns='role'),'Laser','meril','Company Name Only',role='Importer Only').empty

def test_product_scope_match_modes_and_all_fields_license_search():
    frame=pd.DataFrame([
        {'devicename':'Laser catheter','brandname':'Alpha','address':'Meril','str_licence_no':'MD-123'},
        {'devicename':'Catheter laser','brandname':'Beta','address':'Meril','str_licence_no':'MD-456'},
        {'devicename':'Laser','brandname':'Gamma','address':'Other','str_licence_no':'MD-789'},
    ])
    assert len(search_approved_devices(frame,'laser catheter','','Product Name Only',ai_mode=False,match_mode='all_words'))==2
    assert len(search_approved_devices(frame,'laser catheter','','Product Name Only',ai_mode=False,match_mode='exact'))==1
    assert len(search_approved_devices(frame,'laser catheter','','Product Name Only',ai_mode=False,match_mode='any_words'))==3
    assert search_approved_devices(frame,'MD-123','','All Fields',ai_mode=False,match_mode='exact').index.tolist()==[0]
    assert search_approved_devices(frame,'MD-123','','Product Name Only',ai_mode=False,match_mode='exact').empty

def test_fda_matching_modes_and_safe_quoting():
    from research_engine import build_fda_query
    assert build_fda_query('laser catheter','Meril',ai_mode=False,match_mode='exact')=='device_name:"laser catheter" AND applicant:"Meril"'
    assert '(device_name:"laser" OR device_name:"catheter")' in build_fda_query('laser catheter','',ai_mode=False,match_mode='any_words')
    assert '(device_name:"laser" AND device_name:"catheter")' in build_fda_query('laser catheter','',ai_mode=False)
    assert build_fda_query('','Meril Life',ai_mode=True)=='(applicant:"Meril" AND applicant:"Life")'
    assert '\\"' in build_fda_query('laser "system"','',ai_mode=False,match_mode='exact')

def test_punctuation_and_null_columns_do_not_match_everything():
    from research_engine import robust_dataframe_search
    frame=pd.DataFrame({'devicename':['Laser','++control',None]})
    assert robust_dataframe_search(frame,'+++',['devicename']).empty
    assert robust_dataframe_search(frame,'nan',['devicename'],ai_mode=False).empty
    assert robust_dataframe_search(frame,'laser',['missing'],ai_mode=False).empty


def test_bot_company_filter_matches_the_same_literal_applicant_constraint():
    import api
    matches,_=api.filter_cdsco_batch(FRAME,'manufacturer','Laser','Meril')
    assert matches.index.tolist()==[0]
