export type ApprovalStatus = "pending_review" | "approved" | "rejected";
export type ProcessingStatus = "pending" | "processing" | "completed" | "failed";
export type ReimagineStatus = "idle" | "generating";

export interface ScrapedPost {
  id: number;
  source_id: number;
  post_link: string;
  post_text: string | null;
  image_url: string | null;
  timestamp: string | null;
  approval_status: ApprovalStatus;
  reviewed_at: string | null;
  created_at: string;
}

export interface ImageVersion {
  id: number;
  image_path: string;
  created_at: string;
}

export interface ProcessedPost {
  id: number;
  scraped_post_id: number | null;
  source_id: number | null;
  source_label: string | null;
  rewritten_post: string | null;
  hooks: string | null;
  hashtags: string[] | null;
  generated_image_url: string | null;
  reimagine_status: ReimagineStatus;
  status: ProcessingStatus;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface FullPost {
  scraped_post_id: number;
  source_id: number;
  post_link: string;
  original_text: string | null;
  original_image_url: string | null;
  post_timestamp: string | null;
  approval_status: ApprovalStatus;
  processed_post_id: number | null;
  rewritten_post: string | null;
  hooks: string | null;
  hashtags: string[] | null;
  generated_image_url: string | null;
  download_image_url: string | null;
  copy_ready_text: string | null;
  reimagine_status: ReimagineStatus;
  image_versions: ImageVersion[];
  status: ProcessingStatus | "unprocessed";
}
