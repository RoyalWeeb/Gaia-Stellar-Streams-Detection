"""Regenerate the project report from executed outputs (requires reportlab)."""
from pathlib import Path
import json
from xml.sax.saxutils import escape
import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image, KeepTogether
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.graphics.shapes import Drawing, Rect, Line, String, Polygon

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / 'outputs/demo/results'
s = json.loads((RESULTS/'summary.json').read_text())
e = json.loads((RESULTS/'toy_evaluation.json').read_text())
cat = pd.read_csv(RESULTS/'candidate_catalog.csv')
NAVY = colors.HexColor('#171138'); TEAL = colors.HexColor('#0f9e9a')
INK = colors.HexColor('#182338'); MUTED = colors.HexColor('#526178')
PALE = colors.HexColor('#eff6f8'); WHITE = colors.white
from matplotlib import font_manager
for name, weight, slant in [('Body','normal','normal'), ('Bold','bold','normal'), ('Italic','normal','italic')]:
    font = font_manager.findfont(font_manager.FontProperties(family='DejaVu Sans', weight=weight, style=slant))
    pdfmetrics.registerFont(TTFont(name, font))
pdfmetrics.registerFontFamily('Body',normal='Body',bold='Bold',italic='Italic',boldItalic='Bold')
pdfmetrics.registerFontFamily('Bold',normal='Bold',bold='Bold',italic='Italic',boldItalic='Bold')
styles = getSampleStyleSheet()
styles.add(ParagraphStyle('Text', fontName='Body', fontSize=10.2, leading=14, textColor=INK, spaceAfter=9))
styles.add(ParagraphStyle('SmallText', parent=styles['Text'], fontSize=8.5, leading=12, spaceAfter=7))
styles.add(ParagraphStyle('Heading', fontName='Bold',fontSize=23,leading=29,textColor=NAVY,spaceAfter=14))
styles.add(ParagraphStyle('Sub', fontName='Bold',fontSize=12.2,leading=17,textColor=TEAL,spaceBefore=9,spaceAfter=7))
styles.add(ParagraphStyle('Cell',fontName='Body',fontSize=8.5,leading=12,textColor=INK))
styles.add(ParagraphStyle('HeadCell',parent=styles['Cell'],fontName='Bold',textColor=WHITE))
styles.add(ParagraphStyle('CodeBlock',fontName='Courier',fontSize=8.1,leading=12,textColor=INK,backColor=PALE,borderPadding=12,spaceBefore=8,spaceAfter=12))
styles.add(ParagraphStyle('CoverTitle',fontName='Bold',fontSize=32,leading=41,textColor=WHITE,spaceAfter=20))
styles.add(ParagraphStyle('CoverText',fontName='Body',fontSize=11,leading=17,textColor=colors.HexColor('#d6e7ef'),spaceAfter=14))
styles.add(ParagraphStyle('CoverEyebrow',fontName='Bold',fontSize=9,leading=14,textColor=colors.HexColor('#42e4dd'),spaceAfter=22))

story=[]
def p(t, style='Text'): return Paragraph(t, styles[style])
def add(t, style='Text'): story.append(p(t,style))
def h(t): add(t,'Sub')
def page(number,title):
    story.append(PageBreak()); add(f'{number:02d} / PROJECT REPORT','SmallText'); add(title,'Heading')
def table(headers, rows, widths=None):
    data=[[p(escape(str(v)),'HeadCell') for v in headers]]
    data += [[p(escape(str(v)),'Cell') for v in row] for row in rows]
    t=Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),NAVY),('VALIGN',(0,0),(-1,-1),'TOP'),
                          ('LEFTPADDING',(0,0),(-1,-1),9),('RIGHTPADDING',(0,0),(-1,-1),9),
                          ('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),
                          ('ROWBACKGROUNDS',(0,1),(-1,-1),[PALE,WHITE]),('LINEBELOW',(0,0),(-1,0),1,TEAL)]))
    story.append(t);story.append(Spacer(1,10))
def code(t): add(escape(t).replace('\n','<br/>').replace(' ','&nbsp;'),'CodeBlock')

class PageCanvas(canvas.Canvas):
    def __init__(self,*a,**kw): super().__init__(*a,**kw);self.saved=[]
    def showPage(self):
        self.saved.append(dict(self.__dict__));self._startPage()
    def save(self):
        total=len(self.saved)
        for state in self.saved:
            self.__dict__.update(state)
            self.setFont('Body',8)
            self.setFillColor(colors.HexColor('#8da6b9') if self._pageNumber==1 else MUTED)
            self.drawString(52,30,'GAIA DR3  |  UNSUPERVISED MACHINE LEARNING')
            self.drawRightString(543,30,f'{self._pageNumber} / {total}')
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

def background(c,doc):
    if doc.page==1:
        c.setFillColor(NAVY);c.rect(0,0,595.28,841.89,fill=1,stroke=0)
        for x,y,r in [(480,735,2),(522,650,2),(440,690,1.3),(390,750,1),(465,585,2),(535,775,1),(400,618,1.5)]:
            c.setFillColor(colors.HexColor('#42e4dd')); c.circle(x,y,r,fill=1,stroke=0)
        c.setStrokeColor(TEAL); c.line(52,112,543,112)
    else:
        c.setFillColor(WHITE);c.rect(0,0,595.28,841.89,fill=1,stroke=0)
        c.setStrokeColor(TEAL);c.setLineWidth(2);c.line(52,794,543,794)

# 1 - cover and abstract
story.append(Spacer(1,68))
add('IMPLEMENTED PROJECT / OCTOBER 2026','CoverEyebrow')
add('Discovering<br/>Stellar Streams<br/>in Gaia DR3','CoverTitle')
add('A reproducible Python pipeline for clustering stellar positions and motions in Galactocentric phase space.','CoverText')
story.append(Spacer(1,12))
metrics=Table([[p('3,313<br/><font size="9">selected toy stars</font>','CoverText'),
                p('3 / 3<br/><font size="9">toy trails recovered</font>','CoverText'),
                p('17<br/><font size="9">checks passed</font>','CoverText')]],colWidths=[163,164,164])
metrics.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#27214d')),('BOX',(0,0),(-1,-1),.7,TEAL),
                            ('LEFTPADDING',(0,0),(-1,-1),14),('TOPPADDING',(0,0),(-1,-1),14)]))
story.append(metrics);story.append(Spacer(1,23))
add('<b>Abstract</b>','CoverText')
add('The supplied proposal is implemented as an end-to-end candidate-search pipeline: Gaia ADQL retrieval, quality filtering, physical coordinate conversion, robust scaling, UMAP embedding, HDBSCAN clustering, reproducibility checks and candidate exploration. A fully executed offline experiment demonstrates the software on synthetic observations. Three injected trails are recovered, while additional background groups reveal why original-space checks and scientific follow-up are essential.','CoverText')
add('<b>Evidence boundary:</b> bundled results are synthetic. No real Gaia stream discovery, named-stream recovery, 20-stream catalog, or 2.1-million-star sample is claimed.','CoverText')

# 2 - motivation
page(2,'Problem, objectives and scope')
h('Why stellar streams matter')
add('Stellar streams are elongated tidal debris from disrupted dwarf galaxies or star clusters. Their stars can remain related in position and motion after becoming widely separated on the sky. Tracing such debris helps investigate the Milky Way\'s accretion history and gravitational structure. Streams are generally unbound; a dense group is not automatically a physically bound system.')
h('The computational problem')
add('The Gaia catalog contains a large, heterogeneous stellar population. Small coherent groups compete with the field distribution, observational errors, incomplete radial-velocity coverage and selection effects. The number of genuine structures is unknown, so the proposal adopts density-based clustering rather than a prescribed cluster count.')
table(['Objective','Concrete implementation'],[
 ['Reliable sample selection','Finite measurements; RUWE, parallax S/N and radial-velocity uncertainty cuts.'],
 ['Physically meaningful features','Astropy converts observables into x, y, z, vx, vy and vz.'],
 ['Unsupervised candidate search','UMAP local-neighborhood embedding followed by HDBSCAN.'],
 ['Reviewable results','All selected stars, candidate catalog, diagnostics and interactive plots.'],
 ['Reproducibility and diagnostics','Input hashes, explicit parameters, seed stability and original-space checks.']],[150,341])
h('Completed experiment versus research ambition')
add('The software and offline experiment are completed. The public Gaia query path is implemented and unit-tested with mocked archive responses; a live ESA download has not been performed in this environment. No independently obtained astronomical membership catalog was available for real-stream validation.')
add('The proposal\'s 20+ streams, named examples and million-star working sample remain scientific targets. Full-scale clustering, uncertainty-aware inference and confirmed new discovery require additional data and investigation.')

# 3 - data
page(3,'Data selection and coordinate frame')
add('The real-data source is gaiadr3.gaia_source, retrieved through public Gaia TAP+ queries. Gaia DR3 provides radial velocities for about 33.8 million sources [1,2]. A complete six-dimensional sample therefore requires the radial-velocity subset rather than the entire Gaia catalog.')
table(['Observable','Unit / requirement'],[
 ['source_id','Exact Gaia DR3 decimal identifier; preserved as string.'],['ra, dec','ICRS sky position in degrees; valid coordinate ranges.'],
 ['parallax, parallax_error','mas; positive values and consistent S/N above 5.'],['pmra, pmdec','mas/year; pmra already includes cos(dec).'],
 ['radial_velocity','km/s; finite and present.'],['radial_velocity_error','Positive and below 5 km/s.'],['ruwe','Positive and below 1.4.'],
 ['phot_g_mean_mag','Optional retained magnitude; excluded from learning.']],[180,311])
h('Explicit Galactocentric convention [4]')
table(['Parameter','Value'],[['Sun-center distance','8.122 kpc'],['Solar height','20.8 pc'],['Solar velocity','(12.9, 245.6, 7.78) km/s'],['Galactic-center direction','RA 266.4051 deg; Dec -28.936175 deg'],['Roll','0 deg']],[180,311])
add('The baseline distance is d(kpc) = 1 / parallax(mas). Coordinates and velocity differentials are transformed with Astropy, and only then is abs(z) > 3 kpc applied. The adopted Cartesian axes put the Sun approximately on negative x. Frame parameters are saved with every run.')
add('Inverse parallax is an educational approximation. No parallax zero-point correction, probabilistic distance model or covariance propagation is applied. Strict parallax and radial-velocity cuts restrict the accessible distant-halo population.','SmallText')

# 4 - methods
page(4,'Methodology and pipeline')
add('The learner receives six physical features, with no truth labels, sky magnitudes or identifiers. Spatial values are in kpc and velocities in km/s. Robust scaling reduces dependence on arbitrary numerical units.')
code('X = [x, y, z, vx, vy, vz]\nX_scaled[j] = (X[j] - median(X[j])) / IQR(X[j])\nX_weighted = X_scaled * [w_pos, w_pos, w_pos, w_vel, w_vel, w_vel]')
d=Drawing(491,200)
steps=[('QUERY + FILTER','ADQL, finite observables, strict quality cuts'),('TRANSFORM + SELECT','Galactocentric 6D features; abs(z) > 3 kpc'),('SCALE + EMBED','Robust feature scaling; UMAP in 3 dimensions'),('CLUSTER + CHECK','HDBSCAN, seed checks, original-6D control'),('CATALOG + REVIEW','Membership CSV, candidate diagnostics, visual explorer')]
for i,(title,subtitle) in enumerate(steps):
    y=164-i*38
    d.add(Rect(0,y,491,32,fillColor=PALE,strokeColor=colors.HexColor('#d1e3e7'),rx=4,ry=4))
    d.add(String(12,y+19,title,fontName='Bold',fontSize=8.8,fillColor=TEAL))
    d.add(String(12,y+6,subtitle,fontName='Body',fontSize=8.2,fillColor=INK))
    if i<4:
        d.add(Line(245,y,245,y-6,strokeColor=TEAL))
        d.add(Polygon([242,y-3,248,y-3,245,y-7],fillColor=TEAL,strokeColor=TEAL))
story.append(d);story.append(Spacer(1,8))
h('UMAP and HDBSCAN [5,6]')
add('UMAP maps local neighborhoods into a lower-dimensional representation. HDBSCAN identifies dense groups and can label low-density points as noise without fixing the number of clusters. The delivered configuration uses leaf selection for finer hierarchy branches; an EOM alternative is available.')
table(['Setting','Delivered default'],[['UMAP components / neighbors','3 / 30'],['UMAP min_dist / metric','0 / Euclidean'],['HDBSCAN minimum cluster size / samples','120 / 20'],['Cluster selection / baseline seed','leaf / 42'],['Extra UMAP seeds','43 and 44']],[290,201])
add('These defaults were explored on the toy dataset only. They are not validated parameters for real Gaia stream discovery. UMAP can change density structure, so the original physical coordinates remain essential to interpretation.','SmallText')

# 5 - implementation
page(5,'Implementation and reproducibility')
table(['Module','Responsibility'],[['archive.py','Public ADQL queries; ordered source-ID pagination; page cache and manifest.'],['preprocessing.py','Exact identifiers, quality cuts, unit-aware coordinates, chunked halo selection.'],['synthetic.py','Reproducible toy observations and a separate truth file.'],['clustering.py','Scaling, UMAP, HDBSCAN, seed membership overlaps and 6D control.'],['validation.py','Synthetic precision/recall diagnostics against known toy truth.'],['pipeline.py / cli.py','CLI, experiment orchestration, provenance and outputs.'],['plots.py / dashboard.py','Static panels, offline HTML and a linked local 3D explorer.']],[160,331])
h('Archive pagination and restart behavior')
add('Each query selects an ordered page where source_id exceeds the last committed ID. The exact ADQL, archive job ID, row count, final ID and file checksum are saved. An interrupted run resumes committed pages with the same settings. Changed settings or corrupted cached pages are rejected.')
add('A random_index upper bound selects an approximate reproducible random subset. A positive download row cap truncates source-ID order and may bias sky coverage; the manifest marks it explicitly. Complete chosen subsets use max_rows=0.')
h('Scale is handled explicitly')
add('CSV preprocessing reads chunks, applies cuts and transforms, and retains the working sample. The learner remains in memory. The default maximum of 100,000 eligible stars prevents accidental unbounded execution. Explicit uniform sampling uses random priorities and records its effect; rare structures can be lost.')
add('VOTable parsing is eager, so large inputs should be converted to CSV. Chunked pandas provides the portable ingestion path. Dask/Vaex-scale processing and distributed or GPU clustering from the proposal are future extensions, not completed capabilities.')
h('Run provenance')
add('summary.json records input SHA-256, exact configuration, frame parameters, selection counts, Python and package versions, elapsed time and scientific status. The project includes a Conda environment file, package metadata, tested direct dependency versions and an executed notebook.')

# 6 - results
page(6,'Executed synthetic demonstration')
add('The synthetic data contain 3,600 broadly distributed field stars and three correlated, elongated toy trails of 240 members each. The generator converts 6D vectors into Gaia-like observations and adds small independent errors. These trails are not dynamically evolved N-body streams.')
table(['Stage','Observed rows'],[['Generated observations',s['selection']['raw_rows']],['After quality cuts',s['selection']['quality_rows']],['After abs(z) > 3 kpc',s['selection']['halo_rows']],['Rejected by quality / non-halo selection',f"{s['selection']['quality_rejected']} / {s['selection']['non_halo_rejected']}"],['HDBSCAN candidates / noise rows',f"{s['n_clusters']} / {s['noise_rows']}"]],[330,161])
story.append(Image(str(RESULTS/'phase_space_overview.png'),width=460,height=306.67));story.append(Spacer(1,9))
add('Figure 1. UMAP, physical position, sky and velocity projections of the selected sample, colored by HDBSCAN assignment. Gray points are noise. Physical panels reveal the broad background groups that can appear compact in an embedding.','SmallText')
add(f"The run selected {s['selection']['selected_rows']:,} stars without sampling. Noise fraction was {s['noise_fraction']:.1%}. Three of the seven candidates had best membership Jaccard of at least 0.5 with a direct-6D cluster. This is descriptive support, not astronomical confirmation.")

# 7 - validation
page(7,'Recovery and validation')
table(['Toy trail','Best candidate','Precision','Recall'],[[f"Trail {r['truth_label']+1}",r['best_cluster_id'],f"{r['best_cluster_precision']:.1%}",f"{r['best_cluster_recall']:.1%}"] for r in e['trail_recovery']],[110,130,125,126])
add(f"All 720 injected trail stars were assigned to their best matching trail group. However, {e['field_false_assignment_fraction']:.1%} of the selected field stars were also assigned somewhere. The complete partition's adjusted Rand index was {e['adjusted_rand_index_including_field']:.3f}; the aggregate score reflects the field being split into several groups.")
table(['Candidate','Members','Seed Jaccard','6D Jaccard','6D support'],[[int(r.cluster_id),int(r.n_members),f'{r.seed_jaccard_mean:.3f}',f'{r.direct_6d_best_jaccard:.3f}','Yes' if r.original_6d_supported else 'No'] for r in cat.itertuples()],[80,85,110,110,106])
add('Jaccard compares membership sets, avoiding dependence on arbitrary label numbers. Seed Jaccard averages best overlaps with seeds 43 and 44. The direct-6D control clusters the same scaled physical features using the same HDBSCAN settings, bypassing UMAP.')
add('The three trail groups have direct-6D Jaccard scores above 0.83. The four broad background groups are below 0.03. Restricting attention descriptively to the three supported groups leaves 62 field stars alongside 720 trail stars, a 2.4% assignment rate among selected field stars. That reduction is specific to this toy experiment and does not establish a general false-positive guarantee.')
h('Historical parameter experiment and interpretation')
add('The initial EOM setting produced two clusters and assigned every selected field star; two injected trails merged into the large background cluster. A retained 16-setting toy comparison led to leaf selection with minimum cluster size 120. Because configuration choice used this synthetic example, recovery metrics are demonstration results rather than an independent generalization test.')
add('Density-based persistence and membership strengths do not establish physical membership. The current interface focuses on candidate exploration; standalone algorithm comparison, published-reference validation and evidence-download panels have been removed.')

# 8 - run
page(8,'How to run and inspect the project')
h('Install and start')
code('python -m venv .venv\n# Activate the environment for your operating system (see README).\npython -m pip install -e ".[notebook,dev]"\npython -m stellar_streams.cli demo --output outputs/my_demo')
add('Python 3.11 or newer is supported by the package metadata; this delivery was verified on Python 3.12.14. Use a fresh output folder to preserve earlier experiments. The bundled demonstration and explorer can be inspected without rerunning the model.')
h('Real Gaia data')
code('python -m stellar_streams.cli fetch --output data/gaia_dr3.csv --max-rows 0\npython -m stellar_streams.cli run --input data/gaia_dr3.csv --output outputs/gaia_run')
add('Public archive retrieval requires internet access. The full command options and data schema are in README.md and docs/DATA_DICTIONARY.md. Start the local dashboard with python -m stellar_streams.cli dashboard --results outputs/gaia_run to inspect saved results without refitting.')
table(['Output','Use'],[['assigned_stars.csv','Inspect every selected star, physical features and assignments.'],['candidate_catalog.csv','Review sizes, persistence, seed and 6D agreement.'],['summary.json','Audit sample selection and run provenance.'],['toy_evaluation.json','Inspect measured synthetic recovery and false assignments.'],['explorer.html','Open locally in a browser for offline interactive plots.'],['Gaia_Stellar_Streams.ipynb','Read the notebook or opt in to a fresh experiment.']],[190,301])
h('Verification completed')
add('Core checks cover strict quality boundaries, missing measurements, exact large identifiers, physical-coordinate round trips, explicit sampling, archive pagination and resume, query sanitization, cache corruption, label permutation and valid zero-cluster behavior. The complete synthetic demo and offline HTML workflow remain supported. See docs/VERIFICATION.md for the current executed checks.')
add('The live ESA service, real-stream recovery, distributed-scale performance and Python 3.11 execution and interactive Jupyter kernel startup were not exercised here. Package resolution selects compatible dependencies on other supported Python versions.','SmallText')

# 9 - limitations
page(9,'Limitations and future work')
h('What the completed project demonstrates')
add('The proposal can be translated into a reproducible, runnable unsupervised candidate-generation system. Physical feature conversion, explicit scaling, unknown cluster count, noise labeling and visible diagnostics are implemented. The synthetic test shows recovery of coherent toy structures and exposes embedding-induced background groups.')
h('What is needed before scientific discovery claims')
table(['Limitation','Next investigation'],[['Distances and uncertainties','Apply appropriate parallax zero-point corrections, probabilistic distances and correlated-error resampling.'],['Selection effects','Model the radial-velocity and quality-cut selection function; test spatially varying field backgrounds [7].'],['Parameter sensitivity','Use independent synthetic populations and field-only controls; sweep neighbors, weights and HDBSCAN settings.'],['Physical interpretation','Integrate candidate orbits in an explicit Galactic potential with Gala; check kinematic gradients and chemical consistency.'],['External evidence','Compare with independently curated stream memberships and verify release-compatible source identities [8].'],['Scale and coverage','Use justified partitions with overlap and reconciliation; benchmark memory and runtime before increasing the sample.']],[170,321])
h('Future extensions from the proposal')
add('Potential extensions include GPU acceleration, learned phase-space embeddings, wider Gaia selections, reruns on future data releases and fusion with spectroscopic surveys. Orbit integration and chemical evidence can help distinguish tidal debris from bound clusters, moving groups and selection artifacts.')
h('Conclusion')
add('The delivered project completes the computational architecture and a transparent offline demonstration. It recovers the three injected toy trails but also assigns background stars, making original-6D controls essential. It provides a starting point for real Gaia research, while confirmed recovery of named streams and new discovery remain untested scientific goals.')

# 10 references
page(10,'References and submitted files')
refs=[
 ('[1]','Gaia Collaboration, Vallenari et al. (2023). Gaia Data Release 3: Summary of the content and survey properties. A&A 674, A1.','https://doi.org/10.1051/0004-6361/202243940'),
 ('[2]','Katz et al. (2023). Gaia Data Release 3: Properties and validation of the radial velocities. A&A 674, A5.','https://arxiv.org/abs/2206.05902'),
 ('[3]','Astroquery. Gaia TAP+ documentation and asynchronous query examples.','https://astroquery.readthedocs.io/en/latest/gaia/gaia.html'),
 ('[4]','Astropy. Description of the Galactocentric coordinate frame and parameter conventions.','https://docs.astropy.org/en/stable/coordinates/galactocentric.html'),
 ('[5]','McInnes, Healy and Melville (2018). UMAP: Uniform Manifold Approximation and Projection for Dimension Reduction.','https://arxiv.org/abs/1802.03426'),
 ('[6]','UMAP clustering guide and scikit-learn-contrib HDBSCAN API.','https://umap-learn.readthedocs.io/en/latest/clustering.html'),
 ('[7]','Castro-Ginard et al. (2023). Estimating the selection function of Gaia DR3 sub-samples.','https://arxiv.org/abs/2303.17738'),
 ('[8]','Ibata et al. (2021). Charting the Galactic Acceleration Field. I. A Search for Stellar Streams with Gaia DR2 and EDR3 with Follow-up from ESPaDOnS and UVES. ApJ 914, 123.','https://doi.org/10.3847/1538-4357/abfcc2')]
for tag,title,url in refs:
    add(f'<b>{tag}</b> {escape(title)}<br/><font color="#0f9e9a"><link href="{url}">{escape(url)}</link></font>','SmallText')
add('HDBSCAN API: https://hdbscan.readthedocs.io/en/latest/api.html. Documentation checked on 4 October 2026. The supplied ten-slide presentation is the project brief. The Ibata reference illustrates an external catalog; its membership data were not downloaded or validated in this work.','SmallText')
h('Submitted package')
add('Python package and CLI; configurable pipeline; Jupyter notebook; synthetic input and truth; measured result tables; static figure, offline HTML and local dashboard; tests; README; environment specification; data dictionary; proposal mapping; historical parameter experiment; verification notes; this report.')
add('Open README.md first. Every density group retains the status unvalidated_density_candidate. Keep the synthetic and astronomical evidence separate when presenting the project.','SmallText')

out=ROOT/'docs/Project_Report.pdf'
SimpleDocTemplate(str(out),pagesize=(595.28,841.89),leftMargin=52,rightMargin=52,topMargin=64,bottomMargin=54,
                  title='Discovering Stellar Streams in Gaia DR3 - Project Report',author='Gaia Stellar Streams Project').build(story,onFirstPage=background,onLaterPages=background,canvasmaker=PageCanvas)
print(out)
