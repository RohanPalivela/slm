I want to create a fine-tuned SLM that takes notes / text and turns it into questions. This is SPECIFICALLY FOR THE MCAT. So, the notes will be focused on medical ideas / concepts. Then, REALLY GOOD QUESTIONS should be created, ones that seem human made. LLM created questions are known for having very obvious wrong answers and being too "on the nose." The best questions take concepts from the notes, then build on them with expanded MCAT knowledge, then distill it into a question format. The best questions are created by experts, not by people studying. An LLM should be theoretically able to make great questions, but this is an unsolved problem currently

Off the top of my head, I can think of questions that describe symptoms then ask for a diagnoses, questions that start with a theory and then mention a follow up study and ask you to make a conclusion, etc.. These are the type of questions that should automatically be created by the LLM, not generic MCQs.

First, do deep research on all the question types seen in the MCAT. Group them into categories and give them in a format that will be good for agent iteration.

Then generate a prompt that can be given to a base model in order to get the right kind of output. It is a litmus test to see if the SLM should even be created in the first place. Depending on how well it performs, a new idea may have to be brainstormed.

Then, feed this into an agent to decide how/IF this is feasible with an SLM (specifically in terms of scope, like having a bunch of problem types or only 1-2). Do not factor in development time into the consideration, just what is feasible with a model of size about 0.6B-4B parameters. This agent must have a >90% degree of certainty if the model can outperform.

Then, get a subagent brainstormer and a subagent validator to figure out the best plan of action in training the SLM. If the validator does not think the idea is strong/thorough enough, it must give feedback and continue the loop until a good plan is made.

Read the spec for technical constraints as this part of the process is going on: @Train Your Own Small Learning Model.md. 

There is already some data from a different project I have that is all legally scraped. Feel free to look into the @prev_data  folder.

DOCUMENT ALL STEPS AS MARKDOWN FILES IN THE REPO. Feel free to commit and push at any point in the main branch.

Do not ask me for permission if you are working inside the repo or doing searches. Use your discretion for any potentially dangerous actions (which I assume won't happen, this is a read and write set of tasks, no large-scale deletions should be necessary).
