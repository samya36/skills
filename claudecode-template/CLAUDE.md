...
Append below to your CLAUDE.md


## Rules
- Before you do any work, MUST view files in .claude/tasks/context_session_x.md file to get the full context (x being the id of the session we are operate, if file doesnt exist, then create one)
- context_session_x.md should contain most of context of what we did, overall plan, and sub agents will continusly add context to the file
- After you finish the work, MUST update the .claude/tasks/context_session_x.md file to make sure others can get full context of what you did

### Sub agents
You have access to 11 sub agents:
- **vercel-ai-sdk-v5-expert**: all task related to vercel ai sdk HAVE TO consult this agent
- **shadcn-ui-builder**: all task related to UI building & tweaking HAVE TO consult this agent  
- **code-reviewer**: expert code review for full stack applications, security vulnerabilities, and best practices
- **frontend-expert**: frontend development, UI/UX, and user-facing development tasks
- **kiro-design**: create comprehensive feature design documents from approved requirements
- **kiro-executor**: execute specific tasks from design specifications and technical specs with focused implementation
- **kiro-plan**: create actionable implementation task lists from approved feature designs  
- **kiro-requirement**: requirements analysis and specification development using Kiro methodology
- **nextjs-expert**: Next.js application development, optimization, and architecture
- **python-backend-expert**: Python backend systems development using modern tooling like uv
- **technical-documentation-writer**: create comprehensive user manuals, tutorials, and technical documentation

Sub agents will do research about the implementation, but you will do the actual implementation;
When passing task to sub agent, make sure you pass the context file, e.g. '.claude/tasks/session_context_x.md', 
After each sub agent finish the work, make sure you read the related documentation they created to get full context of the plan before you start executing

# Docs
.agent
- Tasks: PRD & implementation plan for each feature
- System: Document the current state of the system (project structure, tech stack, integration points, 
  database schema, and core functionalities such as agent architecture, LLM layer, etc.)
- SOP: Best practices of execute certain tasks (e.g. how to add a schema migration, how to add a new 
  page route, etc.)
- README.md: an index of all the documentations we have so people know what & where to look for things