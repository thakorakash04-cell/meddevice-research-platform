import hashlib
import json
import re
import pandas as pd

def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def get_fda_pmn_link(k): 
    return f"https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/pmn.cfm?ID={k}" if k else None

def get_fda_pdf_link(k):
    if not k or not k.startswith("K"): 
        return None
    yr = k[1:3]
    folder = "pdf" + (yr[1] if yr.startswith("0") else yr)
    return f"https://www.accessdata.fda.gov/cdrh_docs/{folder}/{k}.pdf"

# ─── REGULATORY SYNONYMS DICTIONARY ───────────────────────────────────────────
SYNONYMS = {
    'stent': ['stent', 'scaffold', 'endoprosthesis', 'graft'],
    'bandage': ['bandage', 'dressing', 'gauze', 'tape', 'plaster', 'crepe', 'cohesive'],
    'ablation': ['ablation', 'radiofrequency', 'cryoablation', 'microwave', 'electrosurgical', 'electrode', 'laser ablation'],
    'catheter': ['catheter', 'cannula', 'sheath', 'balloon', 'dilatation', 'guiding'],
    'pacemaker': ['pacemaker', 'pulse generator', 'icd', 'cardiac resynchronization', 'pacing'],
    'implant': ['implant', 'prosthesis', 'fixation', 'screw', 'plate', 'nail', 'joint'],
    'mri': ['mri', 'magnetic resonance', 'scanner'],
    'glove': ['glove', 'examination', 'surgical glove', 'latex', 'nitrile'],
    'syringe': ['syringe', 'needle', 'hypodermic', 'auto-disable', 'injector'],
    'mask': ['mask', 'respirator', 'surgical mask', 'n95', 'face mask'],
    'valve': ['valve', 'heart valve', 'tavr', 'aortic valve', 'mitral'],
    'laser': ['laser', 'diode laser', 'holmium', 'nd:yag', 'argon laser', 'excimer', 'laser system', 'photocoagulator', 'laser fiber']
}

def expand_terms(query_str, enable_synonyms=True):
    if not query_str.strip():
        return []
    q = query_str.lower().strip()
    terms = [q]
    if enable_synonyms:
        words = re.findall(r'\w+', q)
        for w in words:
            for k, syn_list in SYNONYMS.items():
                if w==k or (len(w)>=4 and (k in w or w in k)):
                    terms.extend(syn_list)
    return list(dict.fromkeys(terms))

def robust_dataframe_search(df, query, target_columns, ai_mode=True, match_mode='all_words'):
    if df.empty or not query.strip():
        return df

    q = query.lower().strip()
    words = [w for w in re.findall(r'\w+', q) if len(w) > 0]

    target_columns=[column for column in target_columns if column in df.columns]
    if not target_columns:return df.iloc[0:0].copy()
    corpus = df[target_columns[0]].fillna('').astype(str)
    for col in target_columns[1:]:
        if col in df.columns:
            corpus = corpus + ' ' + df[col].fillna('').astype(str)
    corpus = corpus.str.lower()
    if not words:return df[corpus.str.contains(q,regex=False,na=False)].copy()

    if not ai_mode:
        if match_mode == 'exact':
            mask = corpus.str.contains(q, regex=False, na=False)
        elif match_mode == 'any_words':
            masks = [corpus.str.contains(w, regex=False, na=False) for w in words]
            mask = pd.concat(masks, axis=1).any(axis=1) if masks else pd.Series(True, index=df.index)
        else:
            masks = [corpus.str.contains(w, regex=False, na=False) for w in words]
            mask = pd.concat(masks, axis=1).all(axis=1) if masks else pd.Series(True, index=df.index)
        return df[mask]
    else:
        exact_masks = [corpus.str.contains(w, regex=False, na=False) for w in words]
        exact_match_mask = pd.concat(exact_masks, axis=1).all(axis=1) if exact_masks else pd.Series(False, index=df.index)

        synonym_terms = set()
        for w in words:
            for k, syn_list in SYNONYMS.items():
                if w==k or (len(w)>=4 and (k in w or w in k)):
                    synonym_terms.update(syn_list)

        syn_masks = [corpus.str.contains(t, regex=False, na=False) for t in synonym_terms]
        syn_match_mask = pd.concat(syn_masks, axis=1).any(axis=1) if syn_masks else pd.Series(False, index=df.index)

        combined_mask = exact_match_mask | syn_match_mask
        matched_df = df[combined_mask].copy()

        if not matched_df.empty:
            is_exact = exact_match_mask.loc[matched_df.index]
            matched_df['_rank'] = is_exact.map({True: 0, False: 1})
            matched_df = matched_df.sort_values(by='_rank').drop(columns=['_rank'])

        return matched_df



def company_name_search(df,query):
    """Literal applicant match in the displayed company/address field, never synonyms."""
    query=query.strip()
    if not query:return df
    if 'address' not in df.columns:return df.iloc[0:0].copy()
    return df[df['address'].fillna('').astype(str).str.contains(query,case=False,regex=False,na=False)].copy()

def search_approved_devices(df,device_query,applicant_query,scope,*,ai_mode=True,match_mode='all_words',role=None):
    """Keep company, product and role constraints independent and cumulative."""
    if scope=='Company Name Only':
        matches=company_name_search(df,applicant_query.strip() or device_query.strip())
    else:
        columns=['devicename','brandname','modelname'] if scope=='Product Name Only' else ['devicename','brandname','modelname','str_intended_use','str_licence_no','address']
        columns=[column for column in columns if column in df.columns]
        matches=df.copy()
        if device_query.strip():
            matches=robust_dataframe_search(matches,device_query,columns,ai_mode=ai_mode,match_mode=match_mode) if columns else matches.iloc[0:0]
        matches=company_name_search(matches,applicant_query)
    role_name={'Manufacturer Only':'manufacturer','Importer Only':'importer'}.get(role)
    if role_name:
        if 'role' not in matches.columns:return matches.iloc[0:0].copy()
        matches=matches[matches['role'].fillna('').astype(str).str.strip().str.casefold().eq(role_name)]
    return matches.copy()

def build_fda_query(device_query,applicant_query,*,ai_mode=True,match_mode='all_words'):
    """Honor the UI matching mode while safely quoting values for openFDA."""
    parts=[]
    def quote(value):return json.dumps(value,ensure_ascii=False)
    if device_query.strip():
        text=device_query.strip();words=re.findall(r'\w+',text)
        if ai_mode:
            terms=sorted(expand_terms(text,enable_synonyms=True))
            parts.append('device_name:('+ ' OR '.join(quote(term) for term in terms)+')')
        elif match_mode=='exact' or not words:
            parts.append('device_name:'+quote(text))
        else:
            operator=' OR ' if match_mode=='any_words' else ' AND '
            expressions=['device_name:'+quote(word) for word in words]
            parts.append('('+operator.join(expressions)+')' if len(expressions)>1 else expressions[0])
    if applicant_query.strip():
        words=re.findall(r'\w+',applicant_query.strip()) or [applicant_query.strip()]
        expressions=['applicant:'+quote(word) for word in words]
        parts.append('('+' AND '.join(expressions)+')' if len(expressions)>1 else expressions[0])
    return ' AND '.join(parts)
