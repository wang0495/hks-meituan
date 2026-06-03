const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
        Header, Footer, AlignmentType, LevelFormat, PageNumber,
        HeadingLevel, BorderStyle, WidthType, ShadingType, PageBreak,
        TabStopType, TabStopPosition } = require('docx');
const fs = require('fs');
const path = require('path');

// ===== Improved LaTeX Stripper =====
// Preserves formatting markers: **bold**, *italic*, etc.
function parseInlineFormatting(text) {
  // Returns array of {text, bold, italic} segments
  const segments = [];
  let remaining = text;
  
  while (remaining.length > 0) {
    // Match \textbf{...}, \textit{...}, \emph{...}
    const boldMatch = remaining.match(/\\textbf\{([^}]*)\}/);
    const italicMatch = remaining.match(/\\textit\{([^}]*)\}/);
    const emphMatch = remaining.match(/\\emph\{([^}]*)\}/);
    const underlineMatch = remaining.match(/\\underline\{([^}]*)\}/);
    const ttMatch = remaining.match(/\\texttt\{([^}]*)\}/);
    
    // Find earliest match
    let earliest = null;
    let earliestIdx = remaining.length;
    let matchType = '';
    
    for (const [type, match] of [['bold', boldMatch], ['italic', italicMatch], ['italic', emphMatch], ['underline', underlineMatch], ['tt', ttMatch]]) {
      if (match && match.index < earliestIdx) {
        earliest = match;
        earliestIdx = match.index;
        matchType = type;
      }
    }
    
    if (earliest) {
      // Text before the match
      if (earliestIdx > 0) {
        segments.push({ text: remaining.substring(0, earliestIdx), bold: false, italic: false });
      }
      // The matched content
      segments.push({ text: earliest[1], bold: matchType === 'bold', italic: matchType === 'italic' || matchType === 'underline' });
      remaining = remaining.substring(earliestIdx + earliest[0].length);
    } else {
      segments.push({ text: remaining, bold: false, italic: false });
      break;
    }
  }
  
  return segments;
}

function stripLatexKeepFormatting(text) {
  // First pass: remove commands but preserve formatting intent
  let result = text
    .replace(/\\renewcommand\{[^}]*\}\{[^}]*\}/g, '')
    .replace(/\\abstractname\{[^}]*\}/g, '')
    .replace(/\\newblock\s*/g, ' ')
    .replace(/\\cite\{([^}]*)\}/g, '[$1]')
    .replace(/\\label\{[^}]*\}/g, '')
    .replace(/\\ref\{([^}]*)\}/g, '[$1]')
    .replace(/\\url\{([^}]*)\}/g, '$1')
    .replace(/\\href\{[^}]*\}\{([^}]*)\}/g, '$1')
    .replace(/\\section\{([^}]*)\}/g, '\n## $1\n')
    .replace(/\\subsection\{([^}]*)\}/g, '\n### $1\n')
    .replace(/\\subsubsection\{([^}]*)\}/g, '\n#### $1\n')
    .replace(/\\paragraph\{([^}]*)\}/g, '\n**$1** ')
    .replace(/\\begin\{enumerate\}[^\n]*/g, '')
    .replace(/\\begin\{itemize\}[^\n]*/g, '')
    .replace(/\\end\{enumerate\}/g, '')
    .replace(/\\end\{itemize\}/g, '')
    .replace(/\\item\s*/g, '\n• ')
    .replace(/\\begin\{quote\}/g, '')
    .replace(/\\end\{quote\}/g, '')
    .replace(/\\begin\{thebibliography\}[^}]*\}/g, '')
    .replace(/\\end\{thebibliography\}/g, '')
    .replace(/\\bibitem\{[^}]*\}\s*/g, '\n')
    .replace(/\\maketitle/g, '')
    .replace(/\\usepackage[^ \n]*/g, '')
    .replace(/\\documentclass[^ \n]*/g, '')
    .replace(/\\hypersetup\{[^}]*\}/g, '')
    .replace(/\\definecolor\{[^}]*\}\{[^}]*\}\{[^}]*\}/g, '')
    .replace(/\\usetikzlibrary\{[^}]*\}/g, '')
    .replace(/\\begin\{document\}/g, '')
    .replace(/\\end\{document\}/g, '')
    .replace(/\\begin\{figure\}[^}]*\}/g, '') // skip figure begin
    .replace(/\\end\{figure\}/g, '')
    .replace(/\\begin\{tikzpicture\}[^}]*\}/g, '')
    .replace(/\\end\{tikzpicture\}/g, '')
    .replace(/\\centering/g, '')
    .replace(/\\noindent/g, '')
    .replace(/\\vspace\{[^}]*\}/g, '')
    .replace(/\\hspace\{[^}]*\}/g, '')
    .replace(/\\smallskip/g, '')
    .replace(/\\medskip/g, '')
    .replace(/\\bigskip/g, '')
    // Special symbols
    .replace(/\$\\\sim\$/g, '~')
    .replace(/\$\\geq\$/g, '≥')
    .replace(/\$\\leq\$/g, '≤')
    .replace(/\$\\times\$/g, '×')
    .replace(/\$\\pm\$/g, '±')
    .replace(/\$\\rightarrow\$/g, '→')
    .replace(/\$\\Delta\$/g, 'Δ')
    .replace(/\\geq/g, '≥')
    .replace(/\\leq/g, '≤')
    .replace(/\\times/g, '×')
    .replace(/\\pm/g, '±')
    .replace(/\\rightarrow/g, '→')
    .replace(/\\Delta/g, 'Δ')
    .replace(/\\textasciitilde/g, '~')
    .replace(/\\quad /g, '  ')
    .replace(/\\quad/g, '  ')
    // Quotes
    .replace(/``/g, '\u201c')
    .replace(/''/g, '\u201d')
    .replace(/`/g, '\u2018')
    .replace(/'/g, '\u2019')
    // Dashes
    .replace(/---/g, '\u2014')
    .replace(/--/g, '\u2013')
    // Math mode: $...$ → keep content, strip $
    .replace(/\$([^$]+)\$/g, '$1')
    // Stray backslash commands with optional argument
    .replace(/\\[a-zA-Z]+\{[^}]*\}/g, (match) => {
      const arg = match.match(/\{([^}]*)\}/);
      return arg ? arg[1] : '';
    })
    // Stray backslash commands without argument
    .replace(/\\[a-zA-Z]+/g, '')
    // Clean up remaining artifacts
    .replace(/\\%/g, '%')
    .replace(/\\&/g, '&')
    .replace(/~/g, ' ')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
  
  return result;
}

// ===== Table Parser (三线表) =====
function parseLatexTable(latex) {
  const lines = latex.split('\n').map(l => l.trim()).filter(l => l);
  const caption = [];
  const colSpec = [];
  const dataRows = [];
  let inCaption = false;
  
  for (const line of lines) {
    if (line.match(/\\caption\{(.+)/)) {
      inCaption = true;
      const m = line.match(/\\caption\{(.+)/);
      if (m) caption.push(m[1]);
      continue;
    }
    if (inCaption) {
      caption.push(line);
      if (line.includes('}')) {
        inCaption = false;
        caption[0] = caption.join('').replace(/\\caption\{/, '').replace(/\}$/, '');
      }
      continue;
    }
    if (line.match(/\\begin\{tabular\}\{(.+)\}/)) {
      const m = line.match(/\\begin\{tabular\}\{(.+)\}/);
      if (m) colSpec.push(m[1]);
      continue;
    }
    if (line.startsWith('\\toprule') || line.startsWith('\\midrule') || line.startsWith('\\bottomrule') ||
        line.startsWith('\\hline') || line.startsWith('\\begin') || line.startsWith('\\end') ||
        line.startsWith('\\caption') || line.startsWith('\\label')) continue;
    if (line.startsWith('&')) continue; // stray & line
    
    if (line.includes('&')) {
      const cells = line.split('&').map(c => stripLatexKeepFormatting(c.trim().replace(/\\\\$/, '')));
      if (cells.some(c => c.length > 0)) {
        dataRows.push(cells);
      }
    }
  }
  
  return { caption: stripLatexKeepFormatting(caption[0] || ''), rows: dataRows };
}

// Build a 三线表 (three-line table) for docx
function buildThreeLineTable(tableData) {
  const { caption, rows } = tableData;
  if (!rows || rows.length === 0) return [];
  
  const elements = [];
  const colCount = rows[0].length;
  
  // Borders for 三线表
  const noBorder = { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' };
  const noBorders = { top: noBorder, bottom: noBorder, left: noBorder, right: noBorder };
  const topBottomBorder = { 
    top: { style: BorderStyle.SINGLE, size: 8, color: '000000' }, 
    bottom: { style: BorderStyle.SINGLE, size: 8, color: '000000' }, 
    left: noBorder, right: noBorder 
  };
  const headerBottomBorder = { 
    top: { style: BorderStyle.SINGLE, size: 8, color: '000000' }, 
    bottom: { style: BorderStyle.SINGLE, size: 8, color: '000000' }, 
    left: noBorder, right: noBorder 
  };
  const bottomOnlyBorder = { 
    top: noBorder, 
    bottom: { style: BorderStyle.SINGLE, size: 8, color: '000000' }, 
    left: noBorder, right: noBorder 
  };
  
  // Caption above table
  if (caption) {
    elements.push(new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 200, after: 80 },
      children: [new TextRun({ text: caption, font: 'SimSun', size: 18, bold: true })]
    }));
  }
  
  const tableRows = rows.map((row, rowIdx) => {
    const isHeader = rowIdx === 0;
    const isLast = rowIdx === rows.length - 1;
    
    return new TableRow({
      children: row.map(cell => {
        let borders;
        if (isHeader) {
          borders = headerBottomBorder;
        } else if (isLast) {
          borders = bottomOnlyBorder;
        } else {
          borders = noBorders;
        }
        
        return new TableCell({
          borders,
          margins: { top: 40, bottom: 40, left: 60, right: 60 },
          children: [new Paragraph({
            alignment: AlignmentType.CENTER,
            spacing: { before: 20, after: 20 },
            children: [new TextRun({
              text: cell,
              font: 'Times New Roman',
              size: 18,  // 小五号 9pt
              bold: isHeader
            })]
          })]
        });
      })
    });
  });
  
  // For header-only rows (first data row), we need to add a midrule
  // Actually in 三线表: top rule, header bottom rule, bottom rule
  // The tableRows already handle this through the borders
  
  elements.push(new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    rows: tableRows
  }));
  
  elements.push(new Paragraph({ spacing: { after: 120 }, children: [] }));
  return elements;
}

// ===== Section Parser =====
function parseLatexSections(content) {
  const sections = [];
  const lines = content.split('\n');
  let currentText = [];
  let inTable = false;
  let tableContent = [];
  let skipFigure = false;
  
  function flushText() {
    if (currentText.length > 0) {
      const text = currentText.join('\n').trim();
      if (text && text.length > 1) {
        sections.push({ type: 'text', text });
      }
      currentText = [];
    }
  }
  
  for (const line of lines) {
    const trimmed = line.trim();
    
    // Skip all comments including decorative markers
    if (trimmed.startsWith('%')) continue;
    
    // Skip figure/tikz environments entirely
    if (trimmed.includes('\\begin{figure}') || trimmed.includes('\\begin{tikzpicture}')) {
      flushText();
      skipFigure = true;
      continue;
    }
    if (skipFigure) {
      if (trimmed.includes('\\end{figure}') || trimmed.includes('\\end{tikzpicture}')) {
        skipFigure = false;
      }
      continue;
    }
    
    // Skip non-text LaTeX commands
    if (/^(\\begin\{(abstract|enumerate|itemize|quote|thebibliography|document)})/.test(trimmed)) continue;
    if (/^(\\end\{(abstract|enumerate|itemize|quote|thebibliography|document)})/.test(trimmed)) continue;
    if (/^(\\renewcommand|\\newblock|\\bibitem|\\maketitle|\\usepackage|\\documentclass|\\hypersetup|\\definecolor|\\usetikzlibrary|\\centering|\\noindent|\\vspace|\\hspace|\\smallskip|\\medskip|\\bigskip|\\caption|\\label|\\toprule|\\midrule|\\bottomrule|\\hline)$/.test(trimmed)) continue;
    
    // Table environments
    if (trimmed.includes('\\begin{table}') || trimmed.includes('\\begin{tabular}')) {
      flushText();
      inTable = true;
      tableContent = [];
      continue;
    }
    if (inTable) {
      tableContent.push(trimmed);
      if (trimmed.includes('\\end{table}') || trimmed.includes('\\end{tabular}')) {
        inTable = false;
        const parsed = parseLatexTable(tableContent.join('\n'));
        if (parsed.rows.length > 0) {
          sections.push({ type: 'table', ...parsed });
        }
        tableContent = [];
      }
      continue;
    }
    
    // Section headings
    const h1Match = trimmed.match(/^\\section\{(.+)\}$/);
    const h2Match = trimmed.match(/^\\subsection\{(.+)\}$/);
    const h3Match = trimmed.match(/^\\subsubsection\{(.+)\}$/);
    const pMatch = trimmed.match(/^(?:\\paragraph\{(.+)\})/);
    
    if (h1Match) { flushText(); sections.push({ type: 'h1', text: stripLatexKeepFormatting(h1Match[1]) }); continue; }
    if (h2Match) { flushText(); sections.push({ type: 'h2', text: stripLatexKeepFormatting(h2Match[1]) }); continue; }
    if (h3Match) { flushText(); sections.push({ type: 'h3', text: stripLatexKeepFormatting(h3Match[1]) }); continue; }
    if (pMatch && trimmed.startsWith('\\paragraph')) { 
      flushText(); 
      const pText = stripLatexKeepFormatting(pMatch[1]);
      // paragraph might be followed by text on same line
      const restOfLine = trimmed.replace(/^\\paragraph\{[^}]*\}\s*/, '');
      if (restOfLine.trim()) {
        sections.push({ type: 'phead', text: pText });
        currentText.push(stripLatexKeepFormatting(restOfLine));
      } else {
        sections.push({ type: 'phead', text: pText });
      }
      continue; 
    }
    
    // Skip empty or purely structural lines
    if (!trimmed) continue;
    
    // Regular text
    currentText.push(trimmed);
  }
  
  flushText();
  return sections;
}

// ===== Build Text Runs with Bold/Italic =====
function buildTextRuns(text) {
  const segments = parseInlineFormatting(stripLatexKeepFormatting(text));
  return segments.map(seg => new TextRun({
    text: seg.text,
    font: 'SimSun',
    size: 21,
    bold: seg.bold,
    italics: seg.italic
  }));
}

// ===== Convert Parsed Sections to docx Elements =====
function sectionsToDocxChildren(parsedSections) {
  const children = [];
  
  for (const section of parsedSections) {
    switch (section.type) {
      case 'h1':
        children.push(new Paragraph({
          heading: HeadingLevel.HEADING_1,
          spacing: { before: 360, after: 200 },
          alignment: AlignmentType.LEFT,
          children: [new TextRun({ text: section.text, bold: true, font: 'SimHei', size: 28 })]
        }));
        break;
        
      case 'h2':
        children.push(new Paragraph({
          heading: HeadingLevel.HEADING_2,
          spacing: { before: 240, after: 120 },
          alignment: AlignmentType.LEFT,
          children: [new TextRun({ text: section.text, bold: true, font: 'SimHei', size: 24 })]
        }));
        break;
        
      case 'h3':
        children.push(new Paragraph({
          heading: HeadingLevel.HEADING_3,
          spacing: { before: 180, after: 80 },
          alignment: AlignmentType.LEFT,
          children: [new TextRun({ text: section.text, bold: true, font: 'SimHei', size: 22 })]
        }));
        break;
        
      case 'phead':
        children.push(new Paragraph({
          spacing: { before: 120, after: 60 },
          children: [new TextRun({ text: section.text, bold: true, font: 'SimSun', size: 21 })]
        }));
        break;
        
      case 'text': {
        const paragraphs = section.text.split('\n').filter(p => p.trim());
        for (const para of paragraphs) {
          const trimmed = para.trim();
          if (!trimmed) continue;
          
          // Check if it's a list item
          if (trimmed.startsWith('• ') || trimmed.startsWith('- ')) {
            const content = trimmed.replace(/^[•-]\s*/, '');
            children.push(new Paragraph({
              spacing: { after: 60 },
              indent: { left: 480, hanging: 240 },
              children: buildTextRuns(content)
            }));
          } else {
            children.push(new Paragraph({
              spacing: { after: 80, line: 360 },
              indent: { firstLine: 420 },
              alignment: AlignmentType.JUSTIFIED,
              children: buildTextRuns(trimmed)
            }));
          }
        }
        break;
      }
        
      case 'table': {
        const tableElements = buildThreeLineTable(section);
        children.push(...tableElements);
        break;
      }
    }
  }
  
  return children;
}

// ===== Parse References =====
function parseReferences(mainTex) {
  const refBlock = mainTex.match(/\\begin\{thebibliography\}[\s\S]*?\\end\{thebibliography\}/);
  if (!refBlock) return [];
  
  const refs = [];
  const items = refBlock[0].split('\\bibitem{');
  
  for (const item of items) {
    if (!item.trim()) continue;
    // Extract key
    const keyMatch = item.match(/^([^}]+)/);
    const key = keyMatch ? keyMatch[1] : '';
    // Extract content (everything after the key})
    const content = item.replace(/^([^}]+)\s*/, '').trim();
    if (content) {
      refs.push({
        key,
        text: stripLatexKeepFormatting(content)
      });
    }
  }
  
  return refs;
}

// ===== Main =====
async function main() {
  const paperDir = path.join(__dirname, '..');
  const sectionsDir = path.join(paperDir, 'sections');
  
  // Parse title and author from main.tex
  const mainTex = fs.readFileSync(path.join(paperDir, 'main.tex'), 'utf-8');
  
  // Title, author, affiliation, email - hardcoded for reliability
  const titleEn = 'CityFlow: Expert-Ensemble Multi-Agent Collaboration for Personalized Urban Route Planning';
  const titleZh = 'CityFlow\u4e13\u5bb6\u96c6\u6210\u591a\u667a\u80fd\u4f53\u57ce\u5e02\u8def\u5f84\u89c4\u5212\u6846\u67b6';
  const author = '\u738b\u5176\u9f99';
  const affiliation = '\u5317\u4eac\u5e08\u8303\u5927\u5b66 \u73e0\u6d77\u6821\u533a';
  const email = '13623753581@163.com';
  
  // Parse references
  const references = parseReferences(mainTex);
  
  // Parse section files
  const sectionFiles = [
    'abstract.tex', 'introduction.tex', 'related_work.tex',
    'method.tex', 'experiments.tex', 'discussion.tex', 'conclusion.tex'
  ];
  
  let allSections = [];
  for (const file of sectionFiles) {
    const filePath = path.join(sectionsDir, file);
    if (fs.existsSync(filePath)) {
      const content = fs.readFileSync(filePath, 'utf-8');
      const parsed = parseLatexSections(content);
      allSections.push(...parsed);
    }
  }
  
  // Build body children
  const bodyChildren = sectionsToDocxChildren(allSections);
  
  // Add references section
  bodyChildren.push(new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 360, after: 200 },
    alignment: AlignmentType.LEFT,
    children: [new TextRun({ text: 'References', bold: true, font: 'SimHei', size: 28 })]
  }));
  
  for (let i = 0; i < references.length; i++) {
    bodyChildren.push(new Paragraph({
      spacing: { after: 60 },
      indent: { left: 420, hanging: 420 },
      children: [
        new TextRun({ text: `[${i + 1}] `, font: 'Times New Roman', size: 18 }),
        new TextRun({ text: references[i].text, font: 'Times New Roman', size: 18 })
      ]
    }));
  }
  
  // ===== Create Document =====
  // Title page section (single column, centered)
  const titleSection = {
    properties: {
      page: {
        size: { width: 11906, height: 16838 }, // A4
        margin: { top: 1440, right: 1260, bottom: 1440, left: 1260 }
      },
      column: { count: 1 }
    },
    headers: {
      default: new Header({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [new TextRun({ text: '\u8ba1\u7b97\u673a\u5de5\u7a0b', font: 'SimSun', size: 16, italics: true })]
        })]
      })
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [
            new TextRun({ text: email, font: 'Times New Roman', size: 18 }),
            new TextRun({ text: '    ' }),
            new TextRun({ children: [PageNumber.CURRENT], font: 'Times New Roman', size: 18 })
          ]
        })]
      })
    },
    children: [
      // Chinese title
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { before: 1200, after: 200 },
        children: [new TextRun({ text: titleZh, bold: true, font: 'SimHei', size: 32 })]
      }),
      // English title
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { after: 400 },
        children: [new TextRun({ text: titleEn, bold: true, font: 'Times New Roman', size: 28 })]
      }),
      // Author
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { after: 100 },
        children: [new TextRun({ text: author, font: 'SimSun', size: 24 })]
      }),
      // Affiliation
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { after: 100 },
        children: [new TextRun({ text: affiliation, font: 'SimSun', size: 21 })]
      }),
      // Email
      new Paragraph({
        alignment: AlignmentType.CENTER,
        spacing: { after: 600 },
        children: [new TextRun({ text: email, font: 'Times New Roman', size: 21 })]
      }),
      // Page break
      new Paragraph({ children: [new PageBreak()] })
    ]
  };
  
  // Content section (two columns)
  const contentSection = {
    properties: {
      page: {
        size: { width: 11906, height: 16838 },
        margin: { top: 1440, right: 1260, bottom: 1440, left: 1260 }
      },
      column: {
        count: 2,
        space: 420,
        equalWidth: true,
        separate: true
      }
    },
    headers: {
      default: new Header({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [new TextRun({ 
            text: 'CityFlow: Expert-Ensemble Multi-Agent Collaboration for Personalized Urban Route Planning',
            font: 'Times New Roman', size: 16, italics: true 
          })]
        })]
      })
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [
            new TextRun({ text: '\u738b\u5176\u9f99\uff1aCityFlow\u4e13\u5bb6\u96c6\u6210\u591a\u667a\u80fd\u4f53\u57ce\u5e02\u8def\u5f84\u89c4\u5212\u6846\u67b6', font: 'SimSun', size: 18 }),
            new TextRun({ text: '\t' }),
            new TextRun({ children: [PageNumber.CURRENT], font: 'Times New Roman', size: 18 })
          ]
        })]
      })
    },
    children: bodyChildren
  };
  
  const doc = new Document({
    styles: {
      default: {
        document: {
          run: { font: 'SimSun', size: 21 }
        }
      },
      paragraphStyles: [
        { 
          id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
          run: { size: 28, bold: true, font: 'SimHei' },
          paragraph: { spacing: { before: 360, after: 200 }, outlineLevel: 0 } 
        },
        { 
          id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true,
          run: { size: 24, bold: true, font: 'SimHei' },
          paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1 } 
        },
        { 
          id: 'Heading3', name: 'Heading 3', basedOn: 'Normal', next: 'Normal', quickFormat: true,
          run: { size: 22, bold: true, font: 'SimHei' },
          paragraph: { spacing: { before: 180, after: 80 }, outlineLevel: 2 } 
        },
      ]
    },
    sections: [titleSection, contentSection]
  });
  
  const buffer = await Packer.toBuffer(doc);
  const outputPath = path.join(paperDir, 'cityflow_paper.docx');
  fs.writeFileSync(outputPath, buffer);
  console.log(`Generated: ${outputPath}`);
  console.log(`Total sections: ${allSections.length}`);
  console.log(`References: ${references.length}`);
  console.log(`Title page: ${titleZh}`);
  console.log(`Author: ${author} / ${affiliation} / ${email}`);
}

main().catch(console.error);
