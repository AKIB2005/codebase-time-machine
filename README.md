\# Codebase Time Machine



\## Overview



Codebase Time Machine is a developer-focused tool that reconstructs how a Git codebase evolved over time.



Instead of only showing the current state of a repository, it analyzes Git history to identify:



\- Important commits and milestones

\- Major historical epochs

\- File-level evolution

\- Architectural changes

\- Evidence-based explanations of why changes happened

\- Developer onboarding information

\- Known limitations and unresolved questions



The project uses IBM Bob for evidence-grounded historical analysis while keeping the original Git history as the source of evidence.



\---



\## Problem



Developers joining an existing project can see the current code, but it is often difficult to understand:



\- Why the architecture looks the way it does

\- When important changes were introduced

\- Which commits introduced bugs or later fixes

\- Which components are actually connected

\- What historical context a developer should know



Codebase Time Machine reconstructs this history into a readable report.



\---



\## Project Architecture



```text

Git Repository

&#x20;     |

&#x20;     v

src/git\_analyzer.py

&#x20;     |

&#x20;     v

output/repo\_history.json

&#x20;     |

&#x20;     v

IBM Bob Historical Analysis

&#x20;     |

&#x20;     +--------------------+

&#x20;     |                    |

&#x20;     v                    v

epoch\_analysis.json   why\_analysis.json

&#x20;     |                    |

&#x20;     +---------+----------+

&#x20;               |

&#x20;               v

&#x20;      onboarding\_guide.md

&#x20;               |

&#x20;               v

&#x20;      evolution\_report.html

