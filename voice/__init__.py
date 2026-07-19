"""Voice layer — connects the ElevenLabs Conversational agent to the memory brain.

Three seams (see voice/app.py):
  POST /call/init      conversation-initiation webhook — identify caller, load the
                       confirmed job spec + memory, return the per-call prompt.
  POST /tool/make_offer server tool — enforce the floor/guardrails IN CODE.
  POST /call/postcall  post-call webhook — persist Call + Quote from the transcript
                       and ElevenLabs' extracted data-collection.

The ElevenLabs agent owns hearing/speaking/turn-taking; this service owns who the
caller is, the pricing floor, the memory, and the quote record.
"""
