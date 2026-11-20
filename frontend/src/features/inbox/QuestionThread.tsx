/** The back-and-forth between the agent and the user about one question. */
import type { AgentQuestion } from '@/api/types';
import styles from './QuestionThread.module.css';

interface QuestionThreadProps {
  messages: AgentQuestion['messages'];
}

/** Agent messages on the left with an avatar, the user's replies on the right. */
export function QuestionThread({ messages }: QuestionThreadProps) {
  return (
    <div className={styles.thread}>
      {messages.map((message, index) =>
        message.from === 'you' ? (
          <div key={index} className={styles.messageYou}>
            {message.text}
          </div>
        ) : (
          <div key={index} className={styles.messageAgent}>
            <span className={styles.avatar} aria-hidden="true">
              AA
            </span>
            <p>{message.text}</p>
          </div>
        ),
      )}
    </div>
  );
}
