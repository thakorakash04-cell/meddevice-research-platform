"""Deferred administrator-only downloads for server-owned Ask AI query evidence."""
import io
from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from grounded_ai import execute_query,json_text

def build_research_export(store,actor,tables,query):
    # Called when the download is requested, not while the answer is rendered.
    if store.identity(actor)['role']!='admin':raise PermissionError('Only administrators can download Ask AI tables.')
    store.require_permission(actor,'use_tools');store.require_permission(actor,'download')
    table=next((t for t in tables if t['id']==query.get('table')),None)
    if table is None:raise ValueError('This source table is unavailable. Run the search and ask again.')
    result=execute_query(tables,query,all_rows=True)
    raw_query={'table':query['table'],'filters':query.get('filters',[]),'limit':20}
    if query.get('sort_by') in table['headers']:raw_query.update(sort_by=query['sort_by'],descending=query.get('descending',True))
    matching=execute_query(tables,raw_query,all_rows=True)
    if sum(sum(len(r) for r in rows) for rows in (result['records'],matching['records']))>2_000_000:
        raise ValueError('This export is too large. Narrow the question filters before downloading.')
    workbook=Workbook(write_only=True)
    def write_sheet(name,records):
        sheet=workbook.create_sheet(name);headers=list(records[0]) if records else []
        def cell(value):
            if isinstance(value,str):
                if len(value)>32767:raise ValueError('A text field exceeds Excel’s cell limit. Narrow the exported columns or filters.')
                item=WriteOnlyCell(sheet,value=value);item.data_type='s';return item
            return value
        sheet.append([cell(h) for h in headers])
        for record in records:sheet.append([cell(record.get(h)) for h in headers])
    write_sheet('Result table',result['records'])
    write_sheet('Matching records',matching['records'])
    write_sheet('Query details',[{'Source table':table['name'],'Matched records':matching['matched_records'],'Result rows':result['result_rows'],'Query':json_text(query),'Scope':'Loaded search snapshot, not a complete regulatory registry.'}])
    output=io.BytesIO();workbook.save(output)
    if output.tell()>25_000_000:raise ValueError('The export exceeds 25 MB. Narrow your question filters.')
    if store.identity(actor)['role']!='admin':raise PermissionError('Administrator access is no longer active.')
    store.require_permission(actor,'use_tools');store.require_permission(actor,'download')
    store.log_event(actor,'export','Ask AI research matching records')
    return output.getvalue()
