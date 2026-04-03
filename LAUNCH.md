# I built an open-source citation verification tool. Here's why.

Independent research is going to become plagued by hallucinated citations, non-referenceable sources, and false bedrock foundations — if people aren't able to get support in managing the citations in their work. This is probably true for institutional research and academia too.

Daily, there is news of companies being held liable for exactly these failures. AI used to completely produce documents for external distribution. Not drafts — legal corporate compliance advice presented as findings, based on AI imagination for a best fit in that part of the compliance audit "narrative." Discovered by human review on the receiving end, finding completely hallucinated legal and financial references.

The standard just doesn't exist. So I decided to start contributing to one.

**[citation-sentinel](https://github.com/JustNothingJay/citation-sentinel)** is an open-source tool that audits academic papers by extracting every reference, looking them up on CrossRef and Open Library, validating every DOI, and flagging fabricated or suspicious citations. It runs end-to-end from the command line:

```
sentinel audit ./my-papers/
```

It came out of my own research. I have over 280 citations across papers in the [SECS project](https://secs.observer). I needed to verify every single one of them. I built repetitive repeatable processes, that became repeatable scripts, that became a project. I reverse engineered my own methodology's outputs and turned it into a scalable, usable open source tool. Because nobody asked for it, it also means there is no demand waiting for me to release this, and therefore no hype to attach. Soz.

I am not building because anyone asked me to, but because I do not want my own research being devalued by a lack of awareness of the gaps that I experienced. The methodology that came out of that process is now this tool.

The machine does the exhaustive work: parsing every reference, querying every API, resolving every DOI, scoring every match. The human reviews the output. That's the model — AI handles the 95% that is mechanical so you can focus on the 5% that requires judgement.

I have never built one of these before, and I do not want to say this is the only way. But it is a start.

I welcome any feedback and engagement. If you work with citations — independent, academic, legal, compliance — and this is useful to you, use it. If it's not good enough yet, tell me what's missing.

MIT licensed. Python 3.10+. `pip install citation-sentinel`.

**GitHub:** [JustNothingJay/citation-sentinel](https://github.com/JustNothingJay/citation-sentinel)
