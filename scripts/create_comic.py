from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen.canvas import Canvas

OUT = "data/sample/skyguard_comic.pdf"
W, H = letter
INK = HexColor("#17263d")
BLUE = HexColor("#1967a3")
GOLD = HexColor("#f2b544")
PALE = HexColor("#eef6fb")
RED = HexColor("#d95d52")


def panel(c: Canvas, x, y, width, height, title, body, accent=BLUE):
    c.setFillColor(white)
    c.setStrokeColor(HexColor("#b7c9d7"))
    c.roundRect(x, y, width, height, 12, fill=1, stroke=1)
    c.setFillColor(accent)
    c.roundRect(x, y + height - 27, width, 27, 12, fill=1, stroke=0)
    c.rect(x, y + height - 27, width, 14, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(x + 12, y + height - 18, title)
    c.setFillColor(INK)
    c.setFont("Helvetica", 11)
    text = c.beginText(x + 14, y + height - 49)
    text.setLeading(16)
    for line in body:
        text.textLine(line)
    c.drawText(text)


def speech(c: Canvas, x, y, width, height, text, fill=PALE):
    c.setFillColor(fill)
    c.setStrokeColor(HexColor("#8bb2c8"))
    c.roundRect(x, y, width, height, 14, fill=1, stroke=1)
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(x + width / 2, y + height / 2 - 4, text)


def page_header(c: Canvas, page, subtitle):
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 25)
    c.drawString(48, H - 52, "SKYGUARD")
    c.setFillColor(BLUE)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(49, H - 72, subtitle.upper())
    c.setFillColor(HexColor("#6d7d8c"))
    c.setFont("Helvetica", 9)
    c.drawRightString(W - 48, 31, f"SkyGuard Comics  |  Page {page}")


def build():
    c = Canvas(OUT, pagesize=letter)
    c.setTitle("SkyGuard: The Signal in the Storm")

    page_header(c, 1, "The Signal in the Storm")
    c.setFillColor(HexColor("#dceefa"))
    c.roundRect(48, 505, W - 96, 190, 18, fill=1, stroke=0)
    c.setFillColor(GOLD)
    c.circle(145, 605, 45, fill=1, stroke=0)
    c.setFillColor(BLUE)
    c.circle(145, 605, 27, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(145, 601, "SG")
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 24)
    c.drawString(220, 630, "A storm is coming to Harbor City.")
    c.setFont("Helvetica", 13)
    c.drawString(220, 603, "Only one hero can read the signal in the clouds.")
    speech(c, 220, 535, 310, 45, "SkyGuard: I protect the city with facts!")
    panel(c, 48, 282, 240, 175, "SCENE 1", ["Mara discovers the", "Sky Compass in the", "old lighthouse.", "It stores one charge", "every 24 hours."], RED)
    panel(c, 324, 282, 240, 175, "SCENE 2", ["The compass points", "north-east when a", "storm is 30 minutes", "away. Mara races", "toward Harbor City."], BLUE)
    c.setFillColor(HexColor("#fff8e7"))
    c.roundRect(48, 108, W - 96, 125, 12, fill=1, stroke=0)
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(66, 202, "FACT FILE")
    c.setFont("Helvetica", 12)
    c.drawString(66, 177, "Hero: Mara Vale, known as SkyGuard")
    c.drawString(66, 155, "Home base: Harbor City Lighthouse")
    c.drawString(66, 133, "Special tool: Sky Compass")
    c.showPage()

    page_header(c, 2, "The Choice")
    panel(c, 48, 470, 240, 190, "SCENE 3", ["The storm reaches", "the city early.", "Mara has one charge", "left in the compass", "and two routes to choose."], BLUE)
    panel(c, 324, 470, 240, 190, "SCENE 4", ["Route A crosses", "Market Bridge.", "Route B passes the", "old rail tunnel.", "Both are 2 miles."], RED)
    speech(c, 108, 395, 396, 48, "Mara: Evidence first. Guessing puts people at risk.")
    panel(c, 48, 145, 240, 190, "SCENE 5", ["The compass flashes", "three times near", "Market Bridge.", "Mara learns the", "bridge alarm is broken."], GOLD)
    panel(c, 324, 145, 240, 190, "SCENE 6", ["She repairs the alarm", "and guides the crowd", "to safety before", "the first lightning", "strike."], BLUE)
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(W / 2, 88, "A careful hero checks the signal before acting.")
    c.showPage()

    page_header(c, 3, "After the Storm")
    c.setFillColor(HexColor("#e8f5ec"))
    c.roundRect(48, 470, W - 96, 195, 18, fill=1, stroke=0)
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 23)
    c.drawString(76, 620, "Harbor City is safe.")
    c.setFont("Helvetica", 13)
    c.drawString(76, 590, "The repaired alarm now protects the bridge every night.")
    speech(c, 76, 510, 285, 45, "Mayor Lin: Thank you, SkyGuard!")
    c.setFillColor(GOLD)
    c.circle(482, 560, 62, fill=1, stroke=0)
    c.setFillColor(BLUE)
    c.circle(482, 560, 39, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(482, 554, "SG")
    panel(c, 48, 235, 516, 170, "SKYGUARD RECORD", [
        "The Sky Compass stores one charge every 24 hours.",
        "A storm signal appears 30 minutes before the storm.",
        "Market Bridge and the old rail tunnel are both 2 miles away.",
        "Mara Vale protects Harbor City from the lighthouse.",
    ], BLUE)
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 15)
    c.drawString(48, 172, "THE END")
    c.setFont("Helvetica", 12)
    c.drawString(48, 148, "Next issue: The mystery of the silent lighthouse bell.")
    c.save()


if __name__ == "__main__":
    build()
