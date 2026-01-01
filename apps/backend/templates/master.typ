// Professional Resume Template for Cherrypick
// Single-column ATS-friendly layout with clean typography
// Data source: data.json (TailoredResumeResponse)

#set page(
  margin: (x: 0.75in, y: 0.75in),
  paper: "us-letter"
)

#set text(
  font: "New Computer Modern",
  size: 11pt,
  lang: "en"
)

#set par(
  leading: 0.65em,
  justify: false
)

// Load resume data from JSON
#let resume_data = json("data.json")

// Helper function to format bullet points
#let bullet_point(content) = {
  block(
    inset: (left: 0.2in, top: 0.15em, bottom: 0.15em),
    [• #content]
  )
}

// ============================================
// HEADER SECTION
// ============================================
#align(center)[
  #text(size: 20pt, weight: "bold")[
    #resume_data.candidate_name
  ]
  #v(0.4em)
  #text(size: 10pt)[
    #resume_data.email • #resume_data.phone • #resume_data.location
  ]
]

#v(1.2em)

// ============================================
// EXPERIENCE SECTION
// ============================================
#if resume_data.experiences.len() > 0 [
  #text(size: 14pt, weight: "bold")[EXPERIENCE]
  #line(length: 100%, stroke: 0.8pt)
  #v(0.6em)

  #for exp in resume_data.experiences [
    #grid(
      columns: (1fr, auto),
      column-gutter: 1em,
      [#text(weight: "bold", size: 11pt)[#exp.role_title]],
      [#text(size: 10pt)[#exp.dates]]
    )
    #v(0.2em)
    #text(style: "italic", size: 10.5pt)[#exp.company_name] • #text(size: 10.5pt)[#exp.location]
    #v(0.4em)

    #for bullet in exp.bullet_points [
      #bullet_point(bullet.content)
    ]

    #v(0.7em)
  ]
]

// ============================================
// PROJECTS SECTION
// ============================================
#if resume_data.projects.len() > 0 [
  #text(size: 14pt, weight: "bold")[PROJECTS]
  #line(length: 100%, stroke: 0.8pt)
  #v(0.6em)

  #for proj in resume_data.projects [
    #text(weight: "bold", size: 11pt)[#proj.name]
    #if proj.link != none [
      #text(size: 10pt)[ | ]
      #link(proj.link)[#text(size: 10pt, fill: blue.darken(20%))[Link]]
    ]
    #v(0.2em)

    #text(style: "italic", size: 10.5pt)[#proj.description]
    #v(0.3em)

    #if proj.technologies.len() > 0 [
      #text(size: 10pt, fill: gray.darken(30%))[
        *Technologies:* #proj.technologies.join(", ")
      ]
      #v(0.3em)
    ]

    #for bullet in proj.bullet_points [
      #bullet_point(bullet.content)
    ]

    #v(0.7em)
  ]
]

// ============================================
// SKILLS SECTION
// ============================================
#if resume_data.skills.len() > 0 [
  #text(size: 14pt, weight: "bold")[SKILLS]
  #line(length: 100%, stroke: 0.8pt)
  #v(0.6em)

  #text(size: 10.5pt)[
    #resume_data.skills.map(s => s.name).join(" • ")
  ]

  #v(1em)
]

// ============================================
// EDUCATION SECTION
// ============================================
#if resume_data.education.len() > 0 [
  #text(size: 14pt, weight: "bold")[EDUCATION]
  #line(length: 100%, stroke: 0.8pt)
  #v(0.6em)

  #for edu in resume_data.education [
    #grid(
      columns: (1fr, auto),
      column-gutter: 1em,
      [#text(weight: "bold", size: 11pt)[#edu.degree in #edu.field_of_study]],
      [#text(size: 10pt)[#edu.dates]]
    )
    #v(0.2em)
    #text(size: 10.5pt)[#edu.institution] • #text(size: 10.5pt)[#edu.location]
    #if edu.gpa != none [
      #v(0.2em)
      #text(size: 10pt)[GPA: #edu.gpa]
    ]
    #v(0.6em)
  ]
]
