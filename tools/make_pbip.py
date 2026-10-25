"""Generate the AbsaReviews Power BI project (PBIP: TMDL model + PBIR report)."""
import json
import shutil
import sys
import uuid
from pathlib import Path

OUT = Path(sys.argv[1])
THEME_SRC = Path(sys.argv[2])
NAME = "AbsaReviews"
CSV_URL = "https://raw.githubusercontent.com/KavyaKaushik11/absa-app-reviews/main/data/reviews.csv"
SCHEMA = "https://developer.microsoft.com/json-schemas/fabric"
T = "Reviews"

if OUT.exists():
    shutil.rmtree(OUT)


def write(path, content):
    p = OUT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    if not isinstance(content, str):
        content = json.dumps(content, indent=2, ensure_ascii=False)
    p.write_text(content + "\n", encoding="utf-8")


def tag():
    return str(uuid.uuid4())


def hexid():
    return uuid.uuid4().hex[:20]


# ---------------------------------------------------------------- project file
write(f"{NAME}.pbip", {
    "$schema": f"{SCHEMA}/pbip/pbipProperties/1.0.0/schema.json",
    "version": "1.0",
    "artifacts": [{"report": {"path": f"{NAME}.Report"}}],
    "settings": {"enableAutoRecovery": True},
})

# ---------------------------------------------------------------- semantic model
SM = f"{NAME}.SemanticModel"
write(f"{SM}/.platform", {
    "$schema": f"{SCHEMA}/gitIntegration/platformProperties/2.0.0/schema.json",
    "metadata": {"type": "SemanticModel", "displayName": NAME},
    "config": {"version": "2.0", "logicalId": tag()},
})
write(f"{SM}/definition.pbism", {
    "$schema": f"{SCHEMA}/item/semanticModel/definitionProperties/1.0.0/schema.json",
    "version": "4.0",
    "settings": {},
})
write(f"{SM}/definition/database.tmdl", "database\n\tcompatibilityLevel: 1600")
write(f"{SM}/definition/model.tmdl", f"""model Model
\tculture: en-US
\tdefaultPowerBIDataSourceVersion: powerBI_V3
\tsourceQueryCulture: en-US
\tdataAccessOptions
\t\tlegacyRedirects
\t\treturnErrorValuesAsNull

annotation __PBI_TimeIntelligenceEnabled = 0

annotation PBI_QueryOrder = ["{T}"]

ref table {T}""")

# All per-review columns are calculated in collect_reviews.py. Power BI only picks the
# columns it shows, gives them readable names and sets their types.
# (CSV column, Power BI name, M type, TMDL dataType, formatString, summarizeBy, sortByColumn)
FIELDS = [
    ("platform", "Store", "type text", "string", None, "none", None),
    ("review_id", "Review ID", "type text", "string", None, "none", None),
    ("rating", "Rating", "Int64.Type", "int64", "0", "none", None),
    ("title", "Title", "type text", "string", None, "none", None),
    ("text", "Review", "type text", "string", None, "none", None),
    ("app_version", "App Version", "type text", "string", None, "none", None),
    ("review_date_local", "Review Date", "type datetime", "dateTime", "dd mmm yyyy hh:nn", "none", None),
    ("review_day", "Review Day", "type date", "dateTime", "dd mmm yyyy", "none", None),
    ("month", "Month", "type date", "dateTime", "mmm yyyy", "none", None),
    ("version", "Version", "type text", "string", None, "none", "Version Sort"),
    ("version_sort", "Version Sort", "Int64.Type", "int64", "0", "none", None),
    ("stars", "Stars", "type text", "string", None, "none", "Rating"),
    ("sentiment", "Sentiment", "type text", "string", None, "none", None),   # from VADER
    ("replied", "Replied", "type text", "string", None, "none", None),
    ("hours_to_reply", "Hours to Reply", "type number", "double", "#,0.0", "none", None),
    ("thumbs_up", "Thumbs Up", "Int64.Type", "int64", "#,0", "sum", None),
    ("reply_text", "ABSA Reply", "type text", "string", None, "none", None),
]


def m_list(items):
    return "{" + ", ".join(items) + "}"


M_QUERY = f'''let
    Source = Csv.Document(Web.Contents("{CSV_URL}"), [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Blanks = Table.ReplaceValue(Headers, "", null, Replacer.ReplaceValue, Table.ColumnNames(Headers)),
    Kept = Table.SelectColumns(Blanks, {m_list(f'"{f[0]}"' for f in FIELDS)}),
    Renamed = Table.RenameColumns(Kept, {m_list(f'{{"{f[0]}", "{f[1]}"}}' for f in FIELDS)}),
    Typed = Table.TransformColumnTypes(Renamed, {m_list(f'{{"{f[1]}", {f[2]}}}' for f in FIELDS)}, "en-US")
in
    Typed'''

# (name, dataType, formatString, summarizeBy, sortByColumn)
COLUMNS = [(f[1], f[3], f[4], f[5], f[6]) for f in FIELDS]

# (name, DAX, formatString)
MEASURES = [
    ("Review Count", f"COUNTROWS({T})", "#,0"),
    ("Average Rating", f"AVERAGE({T}[Rating])", "0.00"),
    # Share of all sentiments: ignores a click on the sentiment chart, keeps every other filter.
    ("% Positive", f"DIVIDE(CALCULATE(COUNTROWS({T}), {T}[Sentiment] = \"Positive\"), CALCULATE(COUNTROWS({T}), ALL({T}[Sentiment])))", "0.0%;-0.0%;0.0%"),
    ("% Negative", f"DIVIDE(CALCULATE(COUNTROWS({T}), {T}[Sentiment] = \"Negative\"), CALCULATE(COUNTROWS({T}), ALL({T}[Sentiment])))", "0.0%;-0.0%;0.0%"),
    ("Android Reply Rate", f'DIVIDE(CALCULATE(COUNTROWS({T}), {T}[Replied] = "Yes"), CALCULATE(COUNTROWS({T}), {T}[Store] = "Android"))', "0.0%;-0.0%;0.0%"),
    ("Avg Hours to Reply", f"AVERAGE({T}[Hours to Reply])", "#,0.0"),
    ("Latest Review", f"MAX({T}[Review Date])", "dd mmm yyyy hh:nn"),
]

lines = [f"table {T}", f"\tlineageTag: {tag()}", ""]
for name, dax, fmt in MEASURES:
    lines += [f"\tmeasure '{name}' = {dax}", f"\t\tformatString: {fmt}", f"\t\tlineageTag: {tag()}", ""]
for name, dtype, fmt, summ, sort_by in COLUMNS:
    lines += [f"\tcolumn '{name}'", f"\t\tdataType: {dtype}"]
    if fmt:
        lines.append(f"\t\tformatString: {fmt}")
    lines += [f"\t\tlineageTag: {tag()}", f"\t\tsummarizeBy: {summ}", f"\t\tsourceColumn: {name}"]
    if sort_by:
        lines.append(f"\t\tsortByColumn: '{sort_by}'")
    lines += ["", "\t\tannotation SummarizationSetBy = Automatic", ""]
lines += [f"\tpartition {T} = m", "\t\tmode: import", "\t\tsource ="]
lines += ["\t\t\t\t" + l for l in M_QUERY.splitlines()]
lines += ["", "\tannotation PBI_ResultType = Table"]
write(f"{SM}/definition/tables/{T}.tmdl", "\n".join(lines))

# ---------------------------------------------------------------- report
RP = f"{NAME}.Report"
write(f"{RP}/.platform", {
    "$schema": f"{SCHEMA}/gitIntegration/platformProperties/2.0.0/schema.json",
    "metadata": {"type": "Report", "displayName": NAME},
    "config": {"version": "2.0", "logicalId": tag()},
})
write(f"{RP}/definition.pbir", {
    "$schema": f"{SCHEMA}/item/report/definitionProperties/2.0.0/schema.json",
    "version": "4.0",
    "datasetReference": {"byPath": {"path": f"../{SM}"}},
})
write(f"{RP}/definition/version.json", {
    "$schema": f"{SCHEMA}/item/report/definition/versionMetadata/1.0.0/schema.json",
    "version": "2.0.0",
})
theme = THEME_SRC.stem
(OUT / f"{RP}/StaticResources/SharedResources/BaseThemes").mkdir(parents=True)
shutil.copy(THEME_SRC, OUT / f"{RP}/StaticResources/SharedResources/BaseThemes/{THEME_SRC.name}")
write(f"{RP}/definition/report.json", {
    "$schema": f"{SCHEMA}/item/report/definition/report/1.1.0/schema.json",
    "themeCollection": {"baseTheme": {"name": theme, "reportVersionAtImport": "5.56", "type": "SharedResources"}},
    "layoutOptimization": "None",
    "resourcePackages": [{"name": "SharedResources", "type": "SharedResources",
                          "items": [{"name": theme, "path": f"BaseThemes/{THEME_SRC.name}", "type": "BaseTheme"}]}],
    "settings": {"useStylableVisualContainerHeader": True, "defaultDrillFilterOtherVisuals": True,
                 "allowChangeFilterTypes": True, "useEnhancedTooltips": True, "useDefaultAggregateDisplayName": True},
})


def lit(v):
    return {"expr": {"Literal": {"Value": v}}}


def col(prop):
    return {"Column": {"Expression": {"SourceRef": {"Entity": T}}, "Property": prop}}


def meas(prop):
    return {"Measure": {"Expression": {"SourceRef": {"Entity": T}}, "Property": prop}}


def proj(field):
    prop = next(iter(field.values()))["Property"]
    return {"field": field, "queryRef": f"{T}.{prop}", "nativeQueryRef": prop}


z = [0]


def visual(page, vtype, x, y, w, h, roles, title=None, sort=None, objects=None):
    z[0] += 1000
    name = hexid()
    v = {"visualType": vtype,
         "query": {"queryState": {role: {"projections": [proj(f) for f in fields]} for role, fields in roles.items()}}}
    if sort:
        field, direction = sort
        v["query"]["sortDefinition"] = {"sort": [{"field": field, "direction": direction}], "isDefaultSort": True}
    if objects:
        v["objects"] = objects
    if title:
        v["visualContainerObjects"] = {"title": [{"properties": {"show": lit("true"), "text": lit(f"'{title}'")}}]}
    v["drillFilterOtherVisuals"] = True
    write(f"{RP}/definition/pages/{page}/visuals/{name}/visual.json", {
        "$schema": f"{SCHEMA}/item/report/definition/visualContainer/1.1.0/schema.json",
        "name": name,
        "position": {"x": x, "y": y, "z": z[0], "height": h, "width": w, "tabOrder": z[0]},
        "visual": v,
    })


def slicer(page, column, x, y, w, mode, sort=None):
    visual(page, "slicer", x, y, w, 70, {"Values": [col(column)]}, sort=sort,
           objects={"data": [{"properties": {"mode": lit(f"'{mode}'")}}]})


def page(display_name):
    name = hexid()
    write(f"{RP}/definition/pages/{name}/page.json", {
        "$schema": f"{SCHEMA}/item/report/definition/page/1.1.0/schema.json",
        "name": name, "displayName": display_name, "displayOption": "FitToPage",
        "height": 720, "width": 1280,
    })
    return name


SENTIMENT_COLOURS = {"Negative": "#D64550", "Neutral": "#9AA0A6", "Positive": "#2E9E5B"}


def sentiment_colours():
    """dataPoint colours per Sentiment value, for charts that split by sentiment."""
    return [{
        "properties": {"fill": {"solid": {"color": lit(f"'{colour}'")}}},
        "selector": {"data": [{"scopeId": {"Comparison": {
            "ComparisonKind": 0, "Left": col("Sentiment"), "Right": {"Literal": {"Value": f"'{value}'"}}}}}]},
    } for value, colour in SENTIMENT_COLOURS.items()]


# Page 1: Overview
# Clicking a bar or column (for example "Negative") filters the reviews table at the bottom.
p1 = page("Overview")
slicer(p1, "Store", 20, 10, 300, "Dropdown")
slicer(p1, "Review Day", 340, 10, 440, "Between")
# Newest version first (Version sorts by Version Sort).
slicer(p1, "Version", 800, 10, 300, "Dropdown", sort=(col("Version"), "Descending"))
for i, m in enumerate(["Review Count", "Average Rating", "% Positive", "% Negative"]):
    visual(p1, "card", 20 + i * 315, 90, 295, 95, {"Values": [meas(m)]})
# Ratings are 1-5; the axis goes to 5.5 so lines at 5 do not touch the top edge.
visual(p1, "lineChart", 20, 200, 400, 240,
       {"Category": [col("Month")], "Series": [col("Store")], "Y": [meas("Average Rating")]},
       title="Average rating per month", sort=(col("Month"), "Ascending"),
       objects={"valueAxis": [{"properties": {"start": lit("1D"), "end": lit("5.5D")}}]})
visual(p1, "clusteredColumnChart", 440, 200, 400, 240,
       {"Category": [col("Stars")], "Series": [col("Store")], "Y": [meas("Review Count")]},
       title="Reviews by star rating", sort=(col("Stars"), "Ascending"))
visual(p1, "clusteredBarChart", 860, 200, 400, 240,
       {"Category": [col("Sentiment")], "Y": [meas("Review Count")]},
       title="Reviews by sentiment (click to filter the list)", sort=(col("Sentiment"), "Ascending"),
       objects={"dataPoint": sentiment_colours()})
visual(p1, "tableEx", 20, 455, 1240, 255,
       {"Values": [col(c) for c in ["Review Date", "Store", "Rating", "Sentiment", "Review"]]},
       title="Reviews", sort=(col("Review Date"), "Descending"))

# Page 2: Versions
p2 = page("App versions")
slicer(p2, "Store", 20, 10, 300, "Dropdown")
visual(p2, "clusteredBarChart", 20, 95, 610, 605,
       {"Category": [col("Version")], "Y": [meas("Average Rating")]},
       title="Average rating by app version", sort=(col("Version"), "Descending"))
visual(p2, "barChart", 650, 95, 610, 605,
       {"Category": [col("Version")], "Series": [col("Sentiment")], "Y": [meas("Review Count")]},
       title="Reviews by app version and sentiment", sort=(col("Version"), "Descending"),
       objects={"dataPoint": sentiment_colours()})

# Page 3: Latest reviews
p3 = page("Latest reviews")
slicer(p3, "Store", 20, 10, 300, "Dropdown")
slicer(p3, "Sentiment", 340, 10, 300, "Dropdown")
slicer(p3, "Review Day", 660, 10, 440, "Between")
visual(p3, "tableEx", 20, 95, 1240, 605,
       {"Values": [col(c) for c in ["Review Date", "Store", "Rating", "Sentiment", "Title", "Review", "Version", "Replied", "ABSA Reply"]]},
       title="Latest reviews", sort=(col("Review Date"), "Descending"))

write(f"{RP}/definition/pages/pages.json", {
    "$schema": f"{SCHEMA}/item/report/definition/pagesMetadata/1.0.0/schema.json",
    "pageOrder": [p1, p2, p3],
    "activePageName": p1,
})

write(".gitignore", "**/.pbi/localSettings.json\n**/.pbi/cache.abf")
print("written to", OUT)
