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

M_QUERY = f'''let
    Source = Csv.Document(Web.Contents("{CSV_URL}"), [Delimiter = ",", Columns = 11, Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Headers = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),
    Blanks = Table.ReplaceValue(Headers, "", null, Replacer.ReplaceValue, Table.ColumnNames(Headers)),
    Typed = Table.TransformColumnTypes(Blanks, {{{{"rating", Int64.Type}}, {{"thumbs_up", Int64.Type}}, {{"review_date", type datetimezone}}, {{"reply_date", type datetimezone}}, {{"fetched_at", type datetimezone}}}}, "en-US"),
    // Times are stored in UTC; show them in Uganda time (EAT, UTC+3).
    ToLocal = (x) => if x = null then null else DateTimeZone.RemoveZone(DateTimeZone.SwitchZone(x, 3)),
    Local = Table.TransformColumns(Typed, {{{{"review_date", ToLocal, type datetime}}, {{"reply_date", ToLocal, type nullable datetime}}, {{"fetched_at", ToLocal, type datetime}}}}),
    Stores = Table.TransformColumns(Local, {{{{"store", each if _ = "apple" then "iOS" else "Android", type text}}}}),
    AddDay = Table.AddColumn(Stores, "Review Day", each DateTime.Date([review_date]), type date),
    AddMonth = Table.AddColumn(AddDay, "Month", each Date.StartOfMonth([Review Day]), type date),
    // "8.7.2" becomes "8.7"; Android names like "26.8.1 - August-Release" become "26.8".
    AddVersion = Table.AddColumn(AddMonth, "Version", each if [app_version] = null then "Unknown" else Text.Combine(List.FirstN(Text.Split(Text.Trim(Text.Split([app_version], " - "){{0}}), "."), 2), "."), type text),
    AddVersionSort = Table.AddColumn(AddVersion, "Version Sort", each try Number.From(Text.Split([Version], "."){{0}}) * 1000 + Number.From(Text.Split([Version], "."){{1}}) otherwise 0, Int64.Type),
    AddStars = Table.AddColumn(AddVersionSort, "Stars", each Text.From([rating]) & " star", type text),
    AddSentiment = Table.AddColumn(AddStars, "Sentiment", each if [rating] >= 4 then "Positive" else if [rating] = 3 then "Neutral" else "Negative", type text),
    // Apple's public feed has no developer replies, so iOS shows "No data".
    AddReplied = Table.AddColumn(AddSentiment, "Replied", each if [store] = "iOS" then "No data" else if [reply_text] = null then "No" else "Yes", type text),
    AddHours = Table.AddColumn(AddReplied, "Hours to Reply", each if [reply_date] = null then null else Duration.TotalHours([reply_date] - [review_date]), type nullable number),
    Renamed = Table.RenameColumns(AddHours, {{{{"store", "Store"}}, {{"review_id", "Review ID"}}, {{"rating", "Rating"}}, {{"title", "Title"}}, {{"text", "Review"}}, {{"app_version", "App Version"}}, {{"review_date", "Review Date"}}, {{"thumbs_up", "Thumbs Up"}}, {{"reply_text", "ABSA Reply"}}, {{"reply_date", "Reply Date"}}, {{"fetched_at", "First Seen"}}}})
in
    Renamed'''

# (name, dataType, formatString, summarizeBy, sortByColumn)
COLUMNS = [
    ("Store", "string", None, "none", None),
    ("Review ID", "string", None, "none", None),
    ("Rating", "int64", "0", "none", None),
    ("Title", "string", None, "none", None),
    ("Review", "string", None, "none", None),
    ("App Version", "string", None, "none", None),
    ("Review Date", "dateTime", "dd mmm yyyy hh:nn", "none", None),
    ("Thumbs Up", "int64", "#,0", "sum", None),
    ("ABSA Reply", "string", None, "none", None),
    ("Reply Date", "dateTime", "dd mmm yyyy hh:nn", "none", None),
    ("First Seen", "dateTime", "dd mmm yyyy hh:nn", "none", None),
    ("Review Day", "dateTime", "dd mmm yyyy", "none", None),
    ("Month", "dateTime", "mmm yyyy", "none", None),
    ("Version", "string", None, "none", "Version Sort"),
    ("Version Sort", "int64", "0", "none", None),
    ("Stars", "string", None, "none", "Rating"),
    ("Sentiment", "string", None, "none", None),
    ("Replied", "string", None, "none", None),
    ("Hours to Reply", "double", "#,0.0", "none", None),
]

# (name, DAX, formatString)
MEASURES = [
    ("Review Count", f"COUNTROWS({T})", "#,0"),
    ("Average Rating", f"AVERAGE({T}[Rating])", "0.00"),
    ("% Positive", f"DIVIDE(CALCULATE(COUNTROWS({T}), {T}[Rating] >= 4), COUNTROWS({T}))", "0.0%;-0.0%;0.0%"),
    ("% Negative", f"DIVIDE(CALCULATE(COUNTROWS({T}), {T}[Rating] <= 2), COUNTROWS({T}))", "0.0%;-0.0%;0.0%"),
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


def slicer(page, column, x, y, w, mode):
    visual(page, "slicer", x, y, w, 70, {"Values": [col(column)]},
           objects={"data": [{"properties": {"mode": lit(f"'{mode}'")}}]})


def page(display_name):
    name = hexid()
    write(f"{RP}/definition/pages/{name}/page.json", {
        "$schema": f"{SCHEMA}/item/report/definition/page/1.1.0/schema.json",
        "name": name, "displayName": display_name, "displayOption": "FitToPage",
        "height": 720, "width": 1280,
    })
    return name


# Page 1: Overview
p1 = page("Overview")
slicer(p1, "Store", 20, 10, 300, "Dropdown")
slicer(p1, "Review Day", 340, 10, 440, "Between")
for i, m in enumerate(["Review Count", "Average Rating", "% Positive", "% Negative"]):
    visual(p1, "card", 20 + i * 315, 95, 295, 110, {"Values": [meas(m)]})
visual(p1, "lineChart", 20, 225, 610, 475,
       {"Category": [col("Month")], "Series": [col("Store")], "Y": [meas("Average Rating")]},
       title="Average rating per month", sort=(col("Month"), "Ascending"))
visual(p1, "clusteredColumnChart", 650, 225, 610, 475,
       {"Category": [col("Stars")], "Series": [col("Store")], "Y": [meas("Review Count")]},
       title="Reviews by star rating", sort=(col("Stars"), "Ascending"))

# Page 2: Versions
p2 = page("App versions")
slicer(p2, "Store", 20, 10, 300, "Dropdown")
visual(p2, "clusteredBarChart", 20, 95, 610, 605,
       {"Category": [col("Version")], "Y": [meas("Average Rating")]},
       title="Average rating by app version", sort=(col("Version"), "Descending"))
visual(p2, "barChart", 650, 95, 610, 605,
       {"Category": [col("Version")], "Series": [col("Sentiment")], "Y": [meas("Review Count")]},
       title="Reviews by app version and sentiment", sort=(col("Version"), "Descending"))

# Page 3: Latest reviews
p3 = page("Latest reviews")
slicer(p3, "Store", 20, 10, 300, "Dropdown")
slicer(p3, "Sentiment", 340, 10, 300, "Dropdown")
slicer(p3, "Review Day", 660, 10, 440, "Between")
visual(p3, "tableEx", 20, 95, 1240, 605,
       {"Values": [col(c) for c in ["Review Date", "Store", "Rating", "Title", "Review", "Version", "Replied", "ABSA Reply"]]},
       title="Latest reviews", sort=(col("Review Date"), "Descending"))

write(f"{RP}/definition/pages/pages.json", {
    "$schema": f"{SCHEMA}/item/report/definition/pagesMetadata/1.0.0/schema.json",
    "pageOrder": [p1, p2, p3],
    "activePageName": p1,
})

write(".gitignore", "**/.pbi/localSettings.json\n**/.pbi/cache.abf")
print("written to", OUT)
