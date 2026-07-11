import math, random, sys
from PIL import Image, ImageDraw, ImageFilter

OUT = sys.argv[1] if len(sys.argv) > 1 else "icon_v1.png"
SS = 4
S = 240
N = S * SS

def sc(v): return int(round(v * SS))

# ---------- palette ----------
BG_TOP = (16, 25, 43)
BG_BOT = (9, 13, 22)
FRAME  = (60, 120, 190)
RIM    = (110, 190, 245)      # bright disc rim
DISC_A = (58, 98, 140)        # steel blue disc fill (light, top)
DISC_B = (18, 32, 52)         # steel blue disc fill (dark, bottom)
RING   = (130, 195, 240)      # concentric ring lines
HUB    = (240, 205, 90)       # center hub
LINE   = (150, 175, 200)      # tangent workpiece line
SPARK_CORE = (255, 250, 225)
SPARK_MID  = (255, 205, 80)
SPARK_TIP  = (255, 130, 30)

img = Image.new("RGBA", (N, N), (0,0,0,0))
d = ImageDraw.Draw(img)

# ---------- background gradient (rounded) ----------
bg = Image.new("RGBA", (N, N), (0,0,0,0))
bgd = ImageDraw.Draw(bg)
for y in range(N):
    t = y / (N-1)
    col = tuple(int(BG_TOP[i]*(1-t)+BG_BOT[i]*t) for i in range(3)) + (255,)
    bgd.line([(0,y),(N,y)], fill=col)
# rounded mask
mask = Image.new("L", (N,N), 0)
md = ImageDraw.Draw(mask)
md.rounded_rectangle([sc(3),sc(3),sc(S-3),sc(S-3)], radius=sc(30), fill=255)
img.paste(bg, (0,0), mask)
d = ImageDraw.Draw(img)

# subtle frame
d.rounded_rectangle([sc(3),sc(3),sc(S-3),sc(S-3)], radius=sc(30),
                    outline=FRAME+(150,), width=sc(1.5))

# ---------- geometry ----------
CX, CY = sc(120), sc(106)
R = sc(80)
CONTACT = (CX, CY + R)

# ---------- disc fill (radial-ish vertical gradient inside circle) ----------
disc = Image.new("RGBA", (N,N), (0,0,0,0))
dd = ImageDraw.Draw(disc)
for y in range(CY-R, CY+R):
    t = (y-(CY-R))/(2*R)
    col = tuple(int(DISC_A[i]*(1-t)+DISC_B[i]*t) for i in range(3))+(255,)
    dd.line([(0,y),(N,y)], fill=col)
cmask = Image.new("L",(N,N),0)
ImageDraw.Draw(cmask).ellipse([CX-R,CY-R,CX+R,CY+R], fill=255)
img.paste(disc,(0,0),cmask)
d = ImageDraw.Draw(img)

# outer rim
d.ellipse([CX-R,CY-R,CX+R,CY+R], outline=RIM+(255,), width=sc(4))

# ---------- teeth (short radial ticks INSIDE the rim, as in the original icon) ----------
# Gold ticks sitting just inside the circumference, pointing inward toward centre.
# They never cross the outer edge -> smooth circle, zero spikes outside.
TEETH = 16
tick_out = R - sc(4)      # starts just inside the rim
tick_in  = R - sc(13)     # short inward length
for i in range(TEETH):
    a = 2*math.pi*i/TEETH - math.pi/2
    x0 = CX + math.cos(a)*tick_out; y0 = CY + math.sin(a)*tick_out
    x1 = CX + math.cos(a)*tick_in;  y1 = CY + math.sin(a)*tick_in
    d.line([(x0,y0),(x1,y1)], fill=HUB+(255,), width=sc(2.2))

# ---------- concentric rings (fade toward centre -> reads as wheel, not target) ----------
for rr, wgt, alpha in [(66,2.4,235),(48,2,175)]:
    r = sc(rr)
    d.ellipse([CX-r,CY-r,CX+r,CY+r], outline=RING+(alpha,), width=sc(wgt))
# center hub
hub = sc(12)
d.ellipse([CX-hub,CY-hub,CX+hub,CY+hub], fill=HUB+(255,))
hole = sc(5)
d.ellipse([CX-hole,CY-hole,CX+hole,CY+hole], fill=(20,28,40,255))

# ---------- cut material: STEEL cross-section with 45deg section hatching ----------
# Tangent line = top face of a steel plate; the plate is filled with evenly-spaced
# 45-degree section lines (technical-drawing hatching for steel, per PN/ISO).
ly = CY + R
PL_X0, PL_X1 = sc(15), sc(S-15)
PL_Y0, PL_Y1 = ly, ly + sc(19)
H = PL_Y1 - PL_Y0
STEEL_FILL = (24, 38, 56)
HATCH      = (120, 152, 188)

plate = Image.new("RGBA", (N, N), (0,0,0,0))
pd = ImageDraw.Draw(plate)
pd.rectangle([PL_X0, PL_Y0, PL_X1, PL_Y1], fill=STEEL_FILL+(255,))
# 45-degree hatch (up-right), thin, uniform pitch
pitch = sc(6.5)
xs = PL_X0 - H
while xs < PL_X1 + H:
    pd.line([(xs, PL_Y1), (xs + H, PL_Y0)], fill=HATCH+(255,), width=sc(1.1))
    xs += pitch
pmask = Image.new("L", (N, N), 0)
ImageDraw.Draw(pmask).rectangle([PL_X0, PL_Y0, PL_X1, PL_Y1], fill=255)
img.paste(plate, (0,0), pmask)
d = ImageDraw.Draw(img)
# crisp top face (tangent) + bottom edge of the plate
d.line([(PL_X0, ly), (PL_X1, ly)], fill=LINE+(255,), width=sc(2.6))
d.line([(PL_X0, PL_Y1), (PL_X1, PL_Y1)], fill=(90,112,138,255), width=sc(1.3))

# ---------- sparks ----------
# ---------- sparks: FLAT VECTOR (sharp tapered slivers, palette colours, no glow) ----------
spark_layer = Image.new("RGBA",(N,N),(0,0,0,0))
sd = ImageDraw.Draw(spark_layer)
random.seed(7)

GOLD   = (255, 205, 80)    # flat gold
ORANGE = (255, 138, 42)    # flat orange

def arc_points(x0, y0, ang, speed, gravity, life, steps=9):
    """Ballistic polyline -> gives a natural fan + slight gravity arc + length."""
    vx = math.cos(ang)*speed; vy = math.sin(ang)*speed
    pts=[(x0,y0)]; x,y=x0,y0; t=life/steps
    for _ in range(steps):
        vy += gravity*t; x += vx*t; y += vy*t
        pts.append((x,y))
    return pts

def vspark(pts, base_w, color):
    """Draw a flat, hard-edged tapered sliver following the arc (wide base -> point)."""
    n=len(pts)
    left=[]; right=[]
    for i,(x,y) in enumerate(pts):
        # local direction
        if i < n-1: dx,dy = pts[i+1][0]-x, pts[i+1][1]-y
        else:       dx,dy = x-pts[i-1][0], y-pts[i-1][1]
        L=math.hypot(dx,dy) or 1.0
        nx,ny = -dy/L, dx/L                 # perpendicular
        hw = base_w*(1 - i/(n-1))*0.5       # taper linearly to a sharp point
        left.append((x+nx*hw, y+ny*hw))
        right.append((x-nx*hw, y-ny*hw))
    poly = left + right[::-1]
    sd.polygon(poly, fill=color+(255,))

cx,cy = CONTACT
# Clockwise disc -> surface at bottom contact moves +x; sparks leave tangentially
# up-and-right, fan out, slight gravity arc. Angle 0 = right, negative = up.
GRAV = sc(15)

# main fan
for _ in range(24):
    ang  = math.radians(random.uniform(-54, -12))
    spd  = sc(random.uniform(22, 38))
    life = random.uniform(1.1, 1.8)
    w    = sc(random.uniform(2.0, 3.4))
    col  = ORANGE if random.random() < 0.35 else GOLD
    vspark(arc_points(cx, cy, ang, spd, GRAV, life), w, col)

# long tracers shooting far up-right before the arc bends down
for ang0 in (-44, -32, -22, -13):
    vspark(arc_points(cx, cy, math.radians(ang0 + random.uniform(-3,3)),
           sc(random.uniform(42,52)), GRAV*0.8, random.uniform(1.5,1.9)),
           sc(2.6), GOLD)

# low grazing sparks skimming just above the steel surface
for _ in range(4):
    ang = math.radians(random.uniform(-9, -2))
    vspark(arc_points(cx, cy, ang, sc(random.uniform(30,42)), GRAV*1.5,
           random.uniform(1.2,1.6)), sc(2.0), ORANGE)

# a couple of small back-scatter slivers up-left (impact rebound)
for _ in range(3):
    ang = math.radians(random.uniform(-152, -122))
    vspark(arc_points(cx, cy, ang, sc(random.uniform(15,22)), GRAV*1.4,
           random.uniform(0.7,1.0)), sc(1.8), GOLD)

# small flat flecks (little diamonds) scattered along the plume
def diamond(px, py, r, color):
    sd.polygon([(px,py-r),(px+r,py),(px,py+r),(px-r,py)], fill=color+(255,))
for _ in range(16):
    ang  = math.radians(random.uniform(-58, -6))
    spd  = sc(random.uniform(20, 46)); life = random.uniform(0.6, 1.7)
    p = arc_points(cx, cy, ang, spd, GRAV, life)[-1]
    r = sc(random.uniform(0.9, 1.9))
    diamond(p[0], p[1], r, ORANGE if random.random() < 0.4 else GOLD)

img.alpha_composite(spark_layer)
# small flat origin dot at the contact point (no glow)
ImageDraw.Draw(img).ellipse([cx-sc(2.6),cy-sc(2.6),cx+sc(2.6),cy+sc(2.6)],
                            fill=GOLD+(255,))

# re-apply rounded mask to clip everything
final = Image.new("RGBA",(N,N),(0,0,0,0))
final.paste(img,(0,0),mask)

final = final.resize((S,S), Image.LANCZOS)
final.save(OUT)
print("saved", OUT)
