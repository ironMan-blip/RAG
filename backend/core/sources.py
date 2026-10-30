# Upload origins, keyed by the name clients send; values are source.uuid rows from schema.sql
SOURCE_IDS = {
    'library': '79279d88-e2c3-4a36-9da6-3f02dd71796b',
    'tools': 'b8118424-5418-47b7-a661-8bb768aa8ef5',
    'chat': '20a26963-d20c-469f-8837-620321d589a6'
}

# source uuid -> (label, background color, text color) for the document tag badge
TAG_STYLES = {
    SOURCE_IDS['chat']: ('Chat Interface', '#e0e7ff', '#4f46e5'),
    SOURCE_IDS['library']: ('Library', '#dcfce7', '#16a34a'),
    SOURCE_IDS['tools']: ('Tools', '#fef3c7', '#d97706'),
}
