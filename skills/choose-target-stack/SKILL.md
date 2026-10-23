---
name: choose-target-stack
description: Settle with the user which stack a lifted SAP app's side-by-side code is drafted on (SAP BTP with CAP by default, ABAP Cloud on S/4HANA, AWS, Google Cloud, Azure, or a stack they describe). Use after a CoreLift lift, or when the user wants to change or add a target stack.
---

Clean core is about how an extension touches SAP (released APIs only), not where it runs. Dispositions come from evidence and stay as they are; the stack only decides where side-by-side work goes and how it is built.

1. **Offer.** Read `follows_stack` in `migration/INDEX.json`: only those apps' code goes where the stack says; on-stack apps stay ABAP Cloud on S/4HANA whatever is chosen. If no app follows the stack, say so in one line, keep the default and skip to step 3. Otherwise call `corelift_list_stacks` and, in one short message, name the apps the choice affects, recommend the default (SAP BTP with CAP) unless the user already said where they run, and list the alternatives as short numbered options from their profiles' "When it fits", so the user can answer with a number or "go". Done when the user picked one, or said to go with the recommendation.
2. **New stack.** If the user wants a stack that is not listed, copy the closest shipped profile from [stacks/](stacks/) into `<workspace>/stacks/<id>.md`, rewrite each section for their stack from what they told you, and show them the "Calling SAP" section to confirm. Keep the sections and front matter as they are. Done when `corelift_list_stacks` lists it.
3. **Record.** Call `corelift_choose_stack` with the stack id. Done when it returns the rewritten briefs.

Every profile keeps calls to SAP on released remote APIs. When the user asks for something a profile rules out (direct table reads, RFC to unreleased function modules), explain the clean-core reason and record it as an open question rather than writing it into the profile.
