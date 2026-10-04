"""Build the "Pujo steps" iPhone Shortcut (docs/product/IPHONE_SHORTCUT.md).

    python scripts/make_shortcut.py out.shortcut [site_url]

Actions: Find Health Samples (Steps, today, grouped by day, so iPhone + Watch are de-duplicated)
-> Calculate Statistics (Sum) -> URL  <site>?src=ios_shortcut#steps=<sum>  -> Open URLs.
iOS only imports signed shortcuts, so the shortcut workflow signs the output on a macOS runner
(`shortcuts sign --mode anyone`) and publishes it to app/shortcut/pujo-steps.shortcut.
"""
import plistlib
import sys
import uuid

SITE = "https://shubhgptgrowth.github.io/Durga-Puja-2026/"


def ref(uid, name):
    return {"OutputUUID": uid, "OutputName": name, "Type": "ActionOutput"}


def attachment(uid, name):
    return {"Value": ref(uid, name), "WFSerializationType": "WFTextTokenAttachment"}


def build(site=SITE):
    find, stats, url = (str(uuid.uuid4()).upper() for _ in range(3))
    prefix = f"{site}?src=ios_shortcut#steps="
    actions = [
        {"WFWorkflowActionIdentifier": "is.workflow.actions.filter.health.quantity",
         "WFWorkflowActionParameters": {
             "UUID": find,
             "WFContentItemFilter": {
                 "Value": {
                     "WFActionParameterFilterPrefix": 1,
                     "WFContentPredicateBoundedDate": False,
                     "WFActionParameterFilterTemplates": [
                         {"Bounded": True, "Operator": 4, "Property": "Type", "Removable": False,
                          "Values": {"Enumeration": {"Value": "Steps", "WFSerializationType": "WFStringSubstitutableState"}}},
                         {"Bounded": True, "Operator": 1002, "Property": "Start Date", "Removable": True,
                          "Values": {"Unit": 4}},
                     ],
                 },
                 "WFSerializationType": "WFContentPredicateTableTemplate",
             },
             "WFHKSampleFilteringGroupBy": "Day",
             "WFHKSampleFilteringFillMissing": False,
         }},
        {"WFWorkflowActionIdentifier": "is.workflow.actions.statistics",
         "WFWorkflowActionParameters": {"UUID": stats, "WFStatisticsOperation": "Sum",
                                        "WFInput": attachment(find, "Health Samples")}},
        {"WFWorkflowActionIdentifier": "is.workflow.actions.url",
         "WFWorkflowActionParameters": {
             "UUID": url,
             "WFURLActionURL": {
                 "Value": {"string": prefix + "￼", "attachmentsByRange": {f"{{{len(prefix)}, 1}}": ref(stats, "Statistics")}},
                 "WFSerializationType": "WFTextTokenString",
             }}},
        {"WFWorkflowActionIdentifier": "is.workflow.actions.openurl",
         "WFWorkflowActionParameters": {"WFInput": attachment(url, "URL")}},
    ]
    return {
        "WFWorkflowActions": actions,
        "WFWorkflowClientVersion": "2302.0.4",
        "WFWorkflowMinimumClientVersion": 900,
        "WFWorkflowMinimumClientVersionString": "900",
        "WFWorkflowIcon": {"WFWorkflowIconStartColor": 4282601983, "WFWorkflowIconGlyphNumber": 59511},
        "WFWorkflowImportQuestions": [],
        "WFWorkflowInputContentItemClasses": [],
        "WFWorkflowOutputContentItemClasses": [],
        "WFWorkflowTypes": [],
        "WFWorkflowHasShortcutInputVariables": False,
        "WFQuickActionSurfaces": [],
    }


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "pujo-steps.shortcut"
    with open(out, "wb") as f:
        plistlib.dump(build(sys.argv[2] if len(sys.argv) > 2 else SITE), f, fmt=plistlib.FMT_BINARY)
    print(f"wrote {out}")
