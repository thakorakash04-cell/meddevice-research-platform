import hashlib
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
                if k in w or w in k:
                    terms.extend(syn_list)
    return list(dict.fromkeys(terms))

def robust_dataframe_search(df, query, target_columns, ai_mode=True, match_mode='all_words'):
    if df.empty or not query.strip():
        return df

    q = query.lower().strip()
    words = [w for w in re.findall(r'\w+', q) if len(w) > 0]
    if not words:
        return df

    corpus = df[target_columns[0]].astype(str).fillna('')
    for col in target_columns[1:]:
        if col in df.columns:
            corpus = corpus + ' ' + df[col].astype(str).fillna('')
    corpus = corpus.str.lower()

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
                if k in w or w in k:
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


