"""Ashtami anjali and Sandhi Puja times from the two panjikas, for /guide/dates/ and searches like "sandhi puja time
2026". The times come from data/raw/panjika_2026.toml (through guide.json), each with its source."""
from .common import clock, esc, nice_date
from .metro import day_month


class PanjikaMixin:
    def sandhi_section(self, up):
        """(html, FAQ pairs, plain-text summary) for the dates page, or ('', [], '') when there are no timings."""
        pj = self.g.get("panjika")
        if not pj or not pj.get("panjika"):
            return "", [], ""
        day = self.days[pj["day"]]
        when = nice_date(day["date"], True)
        rows = "".join(
            f"<tr><td><b>{esc(p['name'])}</b> <span lang='bn'>{esc(p.get('name_bn', ''))}</span></td>"
            f"<td>{clock(p['sandhi_start'])} to {clock(p['sandhi_end'])}</td><td>{esc(p['anjali'])}</td>"
            f"<td><a href='{esc(p['source'])}' rel='noopener'>{esc(p['source_name'])}</a></td></tr>" for p in pj["panjika"])
        bm = pj.get("belur_math")
        belur = (f"<p><b>Belur Math</b> (Bisuddha Siddhanta): Ashtami puja from {clock(bm['puja_begins'])}, <b>Kumari Puja at {clock(bm['kumari_puja'])}</b>, "
                 f"Sandhi Puja {clock(bm['sandhi_start'])} to {clock(bm['sandhi_end'])}. Pushpanjali: {esc(bm['anjali'])} "
                 f"<a href='{esc(bm['source'])}' rel='noopener'>Belur Math programme</a></p>") if bm else ""
        both = " or ".join(f"{clock(p['sandhi_start'])} to {clock(p['sandhi_end'])} ({p['name']})" for p in pj["panjika"])
        html = f"""<h2 id="sandhi">Ashtami anjali and Sandhi Puja times, {nice_date(day['date'])}</h2>
<p>Sandhi Puja is the 48 minutes where Ashtami ends and Navami begins, lit with 108 lamps and offered 108 lotuses. This year the two almanacs
Kolkata's pujas follow give different times, so your pandal's time depends on which one its priest follows. Ashtami anjali is always
given <b>before</b> Sandhi Puja begins.</p>
<table class="days"><thead><tr><th>Panjika</th><th>Sandhi Puja</th><th>Ashtami anjali</th><th>Source</th></tr></thead><tbody>{rows}</tbody></table>
{belur}
<p><small>Times as published (checked {day_month(pj["checked"])}). Each puja's priest sets the final time, so ask at your pandal the evening before.</small></p>"""
        qa = [(f"What time is Sandhi Puja on Ashtami {self.year}?",
               f"On {when}: {both}. Which one your pandal follows depends on its priest's panjika."),
              (f"When should I give Ashtami anjali in {self.year}?",
               " ".join(f"{p['name']}: {p['anjali']}" for p in pj["panjika"]))]
        if bm:
            qa.append((f"What time is Kumari Puja at Belur Math in {self.year}?", f"{clock(bm['kumari_puja'])} on {when}, per Belur Math's programme."))
        return html, qa, f"Sandhi Puja on {when}: {both}."
