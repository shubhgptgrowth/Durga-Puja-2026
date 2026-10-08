"""WBTC Puja Parikrama: /guide/wbtc-puja-parikrama/, the state transport corporation's guided puja tours by AC bus,
AC tram and river launch, for searches like "wbtc puja parikrama 2026" and "ac tram puja parikrama fare". The facts
come from data/raw/parikrama_2026.toml, each from the reports it lists; booking is on WBTC's own site."""
import re
import tomllib
from datetime import date
from pathlib import Path

from .common import esc, nice_date
from .metro import day_month
from .knowledge import share_bar

ROOT = Path(__file__).resolve().parents[2]
PARIKRAMA = ROOT / "data" / "raw" / "parikrama_2026.toml"
PATH = "guide/wbtc-puja-parikrama/"


def load_parikrama():
    return tomllib.loads(PARIKRAMA.read_text(encoding="utf-8")) if PARIKRAMA.exists() else None


def days_text(pk):
    """'17, 18 and 20 October', or the package's own words when the reports give no calendar dates."""
    if not pk.get("dates"):
        return pk.get("when", "Dates on the booking page")
    ds = [date.fromisoformat(d) for d in pk["dates"]]
    nums = [str(d.day) for d in ds]
    return (", ".join(nums[:-1]) + " and " + nums[-1] if len(nums) > 1 else nums[0]) + f" {ds[-1]:%B}"


class ParikramaMixin:
    def parikrama_prepare(self):
        self.parikrama = load_parikrama()

    def parikrama_link(self, up, text=None):
        """A link to the page, or '' when there's no parikrama data this year."""
        if not self.parikrama:
            return ""
        return f'<a href="{up}{PATH}">{esc(text or "WBTC Puja Parikrama tours")}</a>'

    def parikrama_row(self, p, up):
        """A facts row for a pandal page when a WBTC tour stops there, else None."""
        tours = [pk for pk in (self.parikrama or {}).get("package", []) if p["id"] in pk.get("pandals", [])]
        if not tours:
            return None
        return ("WBTC tour", "; ".join(f"{esc(pk['name'])}, {esc(days_text(pk))} ({esc(pk['fare'])})" for pk in tours)
                + f". {self.parikrama_link(up, 'Routes and booking')}")

    def parikrama_page(self):
        pr = self.parikrama
        if not pr:
            return
        up = "../../"
        first, last = pr["first_day"], pr["last_day"]
        tram = next((p for p in pr["package"] if p["id"] == "ac_tram"), None)
        modes = "AC bus, AC tram and river launch"
        lead = (f"West Bengal Transport Corporation (WBTC) is running its Puja Parikrama tours from {nice_date(first)} to {nice_date(last, True)}: "
                f"guided rides to the pujas by {modes}, with tickets sold per seat. Below are the routes and fares as reported on "
                f"{day_month(pr['checked'])}. Book, and check the final times and fares, at <a href='{esc(pr['booking_url'])}' rel='noopener'>wbtconline.in</a>.")
        cards = []
        for pk in pr["package"]:
            stops = [x for x in pk.get("pandals", []) if x in self.pandal]
            stops_html = (f"<li><b>Pandals:</b> {', '.join(self.link_pandal(x, up) for x in stops)}</li>" if stops else "")
            cards.append(
                f"<h3>{esc(pk['name'])} <small lang='bn'>{esc(pk.get('name_bn', ''))}</small></h3><ul>"
                f"<li><b>By:</b> {esc(pk['mode'])}</li>"
                f"<li><b>When:</b> {esc(days_text(pk))}</li>"
                f"<li><b>Starts:</b> {esc(pk['departs'])}</li>"
                f"<li><b>Route:</b> {esc(pk['route'])}</li>{stops_html}"
                f"<li><b>Fare:</b> {esc(pk['fare'])}" + (f". {esc(pk['includes'])}" if pk.get("includes") else "") + "</li></ul>")
        table = ("<table class='days'><thead><tr><th>Tour</th><th>When</th><th>Fare</th></tr></thead><tbody>"
                 + "".join(f"<tr><td>{esc(pk['name'])}</td><td>{esc(days_text(pk))}</td><td>{esc(pk['fare'])}</td></tr>" for pk in pr["package"])
                 + "</tbody></table>")
        diy = (f"<h2>Or go on your own</h2><p>A tour suits elders, first-timers and anyone who'd rather not plan. If you'd rather choose your own pandals "
               f"and times, the metro is the cheapest way round: see <a href='{up}guide/metro/'>pandals near every metro station</a>, the "
               f"<a href='{up}guide/'>ready-made walking trails</a> and <a href='{up}guide/best-pandals-{self.year}/'>the best pandals of {self.year}</a>.</p>")
        sources = "<h2>Sources</h2><ul>" + "".join(f"<li><a href='{esc(s['url'])}' rel='noopener'>{esc(s['name'])}</a></li>" for s in pr.get("source", [])) + "</ul>"
        note = (f"<p><small>We aren't connected to WBTC and don't sell these tickets. Fares and times are from news reports as of "
                f"{day_month(pr['checked'])}; WBTC's booking page is the final word.</small></p>")
        qa = [(f"What is WBTC Puja Parikrama {self.year}?",
               f"Guided puja tours run by West Bengal Transport Corporation from {nice_date(first)} to {nice_date(last, True)}, by {modes}. "
               f"You buy a seat and the tour takes you round a set list of pujas."),
              ("How do I book the WBTC Puja Parikrama?", esc(pr["booking"]))]
        if tram:
            names = ", ".join(self.pandal[x]["name"] for x in tram["pandals"] if x in self.pandal)
            qa += [("What is the AC tram puja parikrama fare?", f"{esc(tram['fare'])}, on {esc(days_text(tram))}, starting {esc(tram['departs'])}. {esc(tram.get('includes', ''))}"),
                   ("Which pandals does the AC tram parikrama cover?", f"{esc(names)}, on a loop from Esplanade to Shyambazar and Gariahat.")]
        faq_html, faq_ld = self.faq(qa)
        wa = (f"WBTC Puja Parikrama {self.year}: AC tram, AC bus and launch tours to the pujas, {day_month(first)} to {day_month(last)}. "
              f"Routes and fares:\n{self.url(PATH)}?src=wa_parikrama")
        body = f"""<article>
<h1>WBTC Puja Parikrama {self.year}: AC tram, bus and launch tours</h1>
<p class="lead">{lead}</p>
{share_bar(wa)}
<h2>The tours at a glance</h2>
{table}
<h2>Routes, times and fares</h2>
{''.join(cards)}
<p><a class="cta" href="{esc(pr['booking_url'])}" rel="noopener">Book at wbtconline.in →</a></p>
{diy}
{sources}
{note}
<p><a href="{up}guide/metro/">Pandals by metro station</a> · <a href="{up}guide/late-night-pandal-hopping/">Late-night pandal hopping</a> · <a href="{up}guide/dates/">Durga Puja {self.year} dates</a></p>
{faq_html}
</article>"""
        fare = f" ({tram['fare'].split()[0]})" if tram else ""
        self.page(PATH, f"WBTC Puja Parikrama {self.year}: AC Tram, Bus and Launch Routes and Fares",
                  f"WBTC Puja Parikrama {self.year}, {day_month(first)} to {day_month(last)}: AC tram{fare}, launch, bonedi bari and suburban AC bus tours, "
                  f"with routes, fares and how to book.",
                  body, ld=(faq_ld,), crumbs=(("Durga Puja guide", "guide/"), ("WBTC Puja Parikrama", PATH)), priority=0.85,
                  summary=re.sub(r"<[^>]+>", "", lead), app_link="#plan")
        self.full.append(f"## WBTC Puja Parikrama {self.year}\n{re.sub(r'<[^>]+>', '', lead)}\n"
                         + "\n".join(f"- {pk['name']} ({pk['mode']}): {days_text(pk)}; {pk['departs']}; {pk['fare']}" for pk in pr["package"])
                         + f"\nPage: {self.url(PATH)}\n")
