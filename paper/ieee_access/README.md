# CityFlow - IEEE Access Version

## How to Compile

### Option 1: Overleaf (Recommended)
1. Go to https://www.overleaf.com
2. Click "New Project" → "Upload Project"
3. Upload the `ieee_access.zip` file
4. Click "Recompile" → PDF will be generated automatically

### Option 2: Local LaTeX
Install TeX Live or MiKTeX, then:
```bash
cd ieee_access
pdflatex main.tex
pdflatex main.tex  # run twice for references
```

## File Structure
- `main.tex` - Main document with IEEEtran template, IEEE-format references
- `sections/introduction.tex` - Introduction with contributions
- `sections/related_work.tex` - Related work (6 subsections)
- `sections/method.tex` - System architecture with TikZ diagram
- `sections/experiments.tex` - Experiments (16 subsections, 20 tables)
- `sections/discussion.tex` - Discussion (7 subsections)
- `sections/conclusion.tex` - Conclusion

## Key Differences from Chinese Version
- Pure English (Chinese abstract removed)
- IEEEtran document class
- IEEE reference format (numbered, abbreviated journal names)
- All tables use [!t] placement (IEEE style)
- Grayscale TikZ diagram (print-friendly)
