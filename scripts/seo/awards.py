"""Puja awards: /guide/award-winning-pandals-2026/, for searches like "sharad samman 2026 winners" and "award winning
pandals kolkata". Winners come from data/raw/awards_2026.toml (through guide.json), each with the link it was read in.
Until this year's results are out, the page says so and lists last year's winners."""
import re

from .common import esc
from .knowledge import share_bar


class AwardsMixin:
    @property
    def award_path(self):
        return f"guide/award-winning-pandals-{self.year}/"

    def award_info(self, aid):
        return next((a for a in self.g.get("awards", []) if a["id"] == aid), {"id": aid, "name": aid, "short": aid})

    def award_text(self, w):
        """'Asian Paints Sharad Shamman 2025, Best Puja'."""
        return f"{self.award_info(w['award'])['name']} {w['year']}, {w['category']}"

    def award_row(self, p, up):
        """A facts row for a pandal page when the pandal has won an award, else None."""
        if not p.get("awards"):
            return None
        return ("Awards", "; ".join(f"<a href='{esc(w['source'])}' rel='noopener'>{esc(self.award_text(w))}</a>"
                                    + (f" (theme: {esc(w['theme'])})" if w.get("theme") else "") for w in p["awards"])
                + f". <a href='{up}{self.award_path}'>All winners</a>")

    def awards_page(self):
        awards = self.g.get("awards", [])
        if not awards:
            return
        up = "../../"
        wins = [(p, w) for p in self.g["pandals"] for w in p.get("awards", [])]
        this = [x for x in wins if x[1]["year"] == self.year]
        last = [x for x in wins if x[1]["year"] < self.year]
        prev_year = max((w["year"] for _, w in last), default=self.year - 1)

        def table(rows):
            rows = sorted(rows, key=lambda x: (x[1]["award"], x[1]["category"], x[0]["name"]))
            return ("<table class='days'><thead><tr><th>Pandal</th><th>Award</th><th>Theme</th></tr></thead><tbody>"
                    + "".join(f"<tr><td>{self.link_pandal(p['id'], up)}<br><small>{esc(self.zone[p['zone']]['name'])}</small></td>"
                              f"<td><a href='{esc(w['source'])}' rel='noopener'>{esc(self.award_info(w['award'])['short'])}</a>, {esc(w['category'])}</td>"
                              f"<td>{esc(w.get('theme', ''))}</td></tr>" for p, w in rows)
                    + "</tbody></table>")

        names = " and the ".join(a["name"] for a in awards)
        if this:
            lead = (f"The {self.year} puja award winners so far: {len(this)} Kolkata pandals from the {names}. "
                    f"Each links to the award's own announcement; the list grows as the juries announce.")
        else:
            lead = (f"The {self.year} winners of the {names} haven't been announced yet; they usually come out during the pujas, "
                    f"around Panchami ({esc(self.days['panchami']['date'][8:].lstrip('0'))} October). This page is updated the day they are. "
                    f"Meanwhile, here are last year's ({prev_year}) winners, all in this guide with their best time to visit and nearest metro.")
        how = "<h2>The awards</h2><ul>" + "".join(
            f"<li><b>{esc(a['name'])}</b>: {esc(a.get('announce', ''))} <a href='{esc(a['url'])}' rel='noopener'>Official page</a></li>" for a in awards) + "</ul>"
        sections = (f"<h2>{self.year} winners</h2>{table(this)}" if this else
                    f"<h2>{self.year} winners</h2><p>Not announced yet. Check back during the pujas.</p>")
        if last:
            sections += f"<h2>{prev_year} winners</h2>{table(last)}"
        route = ""
        stops = list(dict.fromkeys(p["id"] for p, _ in (this or last)))
        if stops:
            route = (f"<h2>Visit the winners</h2><p>The winners are spread across the city, so pick two or three in one area. "
                     f"<a href='{up}?src=seo_guide#plan'>Plan a route in the app</a>, or see each pandal's quietest hours: "
                     + ", ".join(self.link_pandal(x, up) for x in stops) + ".</p>")
        qa = [(f"Which pandals won the Sharad Samman in {self.year}?",
               (", ".join(f"{p['name']} ({self.award_info(w['award'])['short']}, {w['category']})" for p, w in this) + ".") if this
               else f"The {self.year} results haven't been announced yet; they usually come out around Panchami."),
              (f"Which pandals won the Asian Paints Sharad Shamman in {prev_year}?",
               ", ".join(p["name"] for p, w in last if w["award"] == "apss") + ".")]
        qa = [q for q in qa if not q[1].startswith(".")]
        faq_html, faq_ld = self.faq(qa)
        wa = f"Durga Puja {self.year} award-winning pandals in Kolkata (Sharad Samman):\n{self.url(self.award_path)}?src=wa_awards"
        body = f"""<article>
<h1>Award-winning Durga Puja pandals {self.year}: Sharad Samman winners</h1>
<p class="lead">{lead}</p>
{share_bar(wa)}
{sections}
{route}
{how}
<p><a href="{up}guide/best-pandals-{self.year}/">Best pandals {self.year}</a> · <a href="{up}guide/themes-{self.year}/">All {self.year} themes</a> · <a href="{up}guide/metro/">Pandals by metro station</a></p>
{faq_html}
</article>"""
        self.page(self.award_path, f"Sharad Samman {self.year} Winners: Award-Winning Durga Puja Pandals in Kolkata",
                  (f"Durga Puja {self.year} award winners in Kolkata: {len(this)} pandals so far." if this else
                   f"Sharad Samman {self.year} winners, updated the day they're announced, plus last year's winners.")
                  + " With themes, best time to visit and nearest metro.",
                  body, ld=(faq_ld,), crumbs=(("Durga Puja guide", "guide/"), (f"Award winners {self.year}", self.award_path)),
                  priority=0.85, summary=re.sub(r"<[^>]+>", "", lead), app_link="")
        self.full.append(f"## Award-winning pandals {self.year}\n{re.sub(r'<[^>]+>', '', lead)}\n"
                         + "\n".join(f"- {p['name']}: {self.award_text(w)}" for p, w in this + last) + f"\nPage: {self.url(self.award_path)}\n")
