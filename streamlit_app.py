"""Streamlit app for FOIA Explorer COVID-19 Emails"""
import streamlit as st
import pandas as pd
import altair as alt
import psycopg2
import datetime
from st_aggrid import AgGrid
from st_aggrid.grid_options_builder import GridOptionsBuilder


title = "Documenting COVID-19 Email Explorer"
st.set_page_config(page_title=title, layout="wide")
st.title(title)
st.markdown("A finding aid for the emails of \
[Documenting COVID-19](https://documentingcovid19.io).")

# initialize database connection - uses st.cache to only run once
@st.cache(allow_output_mutation=True,
          hash_funcs={"_thread.RLock": lambda _: None})
def init_connection():
    return psycopg2.connect(**st.secrets["postgres"])


# perform query - ses st.cache to only rerun once
@st.cache
def run_query(query):
    with conn.cursor() as cur:
        cur.execute(query)
        return cur.fetchall()


@st.cache
def get_list(qry):
    lov = []
    rows = run_query(qry)
    for r in rows:
        lov.append(r[0])
    return(lov)


@st.cache
def get_entity_list(qual):
    return get_list(f'select entity from covid19.entities \
                         where entity_id > 515 and enttype {qual} \
                         order by entity')


@st.cache(hash_funcs={psycopg2.extensions.connection: lambda _: None})
def get_data_table(qry):
    return pd.read_sql_query(qry, conn)


conn = init_connection()

emcnts = """select date(sent) date, count(*) emails from covid19.dc19_emails \
where sent >= '2020-01-01' group by date order by date"""
cntsdf = get_data_table(emcnts)
#cntsdf = pd.read_sql_query(emcnts, conn)
c = alt.Chart(cntsdf).mark_bar().encode(
    x=alt.X('date:T', scale=alt.Scale(domain=('2020-01-01', '2021-06-01'))),
    y=alt.Y('emails:Q', scale=alt.Scale(domain=(0, 500)))
    )
st.altair_chart(c, use_container_width=True)

# build dropdown lists for entities
# state_list = get_list('select state from covid19.states \
# where length(state) = 2 order by state')
# category_list = get_list('select tag from covid19.tags order by upper(tag)')
# file_list = get_list('select distinct foiarchive_file from covid19.files f \
# join covid19.emails e on f.file_id = e.file_id order by foiarchive_file')
# entity_list = get_list('select entity from covid19.entities order by entity')
person_list = get_entity_list("= 'PERSON' ")
org_list = get_entity_list("= 'ORG' ")
loc_list = get_entity_list("in ('GPE', 'LOC', 'NORP', 'FAC') ")


"""**Enter search criteria:**"""
with st.form(key='query_params'):
    cols = st.columns(2)
    begin_date = cols[0].date_input('Start Date:', datetime.date(2020, 3, 19))
    end_date = cols[1].date_input('End Date:', datetime.date(2020, 3, 20))
    # categories = cols[0].multiselect('Categor(ies):', category_list)
    # states = cols[1].multiselect('State(s):', state_list)
    # files = st.multiselect('File(s):', file_list)
    # entities = st.multiselect('Entit(ies):', entity_list)
    persons = st.multiselect('Person(s):', person_list)
    orgs = st.multiselect('Organization(s):', org_list)
    locations = st.multiselect('Location(s):', loc_list)
    query = st.form_submit_button(label='Execute Search')


""" #### Search Results """
entities = persons + orgs + locations
selfrom = """select sent, coalesce(subject, '') subject, pg_cnt,
       coalesce(from_email, '') "from", coalesce(to_emails, '') "to",
       coalesce(topic, '') topic, array[]::text[] entities,
       source_url_email, scrape_url file_description, email_id, file_id,
       file_pg_start pg_number from covid19.dc19_emails """
where = f"where sent between '{begin_date}' and '{end_date}'"
qry_explain = where
where_ent = ''
orderby = 'order by sent'
if entities:
    # build entity in list
    entincl = '('
    for e in entities:
        entincl += f"'{e}', "
    entincl = entincl[:-2] + ')'
    # form subquery
    where_ent = """
    and e.email_id in
        (select eem.email_id
            from covid19.entities ent join covid19.entity_emails eem
                on (ent.entity_id = eem.entity_id)
            where ent.entity in """ + f'{entincl}) '
    qry_explain += f"and email references at least one of {entincl}"
st.write(qry_explain)
# execute query
emqry = selfrom + where + where_ent + orderby
emdf = get_data_table(emqry)
# emdf = pd.read_sql_query(emqry, conn)
# emdf['sent'] = pd.to_datetime(emdf['sent'], utc=True)
# download results as CSV
csv = emdf.to_csv().encode('utf-8')
st.download_button(label="CSV download", data=csv,
                   file_name='foia-covid19.csv', mime='text/csv')
# generate AgGrid
gb = GridOptionsBuilder.from_dataframe(emdf)
gb.configure_default_column(value=True, editable=False)
gb.configure_selection(selection_mode='single', groupSelectsChildren=False)
gb.configure_pagination(paginationAutoPageSize=True)
gb.configure_grid_options(domLayout='normal')
gridOptions = gb.build()

# update_mode='SELECTION_CHANGED',
grid_response = AgGrid(emdf,
                       gridOptions=gridOptions,
                       return_mode_values='AS_INPUT',
                       update_mode='SELECTION_CHANGED',
                       allow_unsafe_jscode=False,
                       enable_enterprise_modules=False)
selected = grid_response['selected_rows']
# st.write(selected)
if selected:
    """### Email Preview"""
    cols = st.columns(4)
    cols[0].markdown('Email in source document:')
    cols[1].markdown(f'{selected[0]["source_url_email"]}')
    cols[0].markdown('Source document description:')
    cols[1].markdown(f'{selected[0]["file_description"]}')
#    st.markdown(f'<iframe src="https://drive.google.com/viewerng/viewer?\
# embedded=true&url=https://foiarchive-covid-19.s3.amazonaws.com/fauci/pdfs/\
# fauci_{pg}.pdf" width="100%" height="1100">', unsafe_allow_html=True)
else:
    st.write('Select row to view email')

"""
### About
All emails and documents that appear in this app are from the [Documenting
COVID-19 project of the Brown Institute for Media Innovation]
(https://documentingcovid19.io), so any use of data from it must attribute the
"Documenting COVID-19 project at The Brown Institute for Media Innovation."

Columbia Univesity's [History Lab](http://history-lab.org) created this app and
associated processing tools under a grant from the Mellon Foundation's [Email
Archives: Building Capacity and Community]
(https://emailarchivesgrant.library.illinois.edu/blog/) program.
"""
