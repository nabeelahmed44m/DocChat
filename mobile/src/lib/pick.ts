/**
 * Document acquisition helpers.
 *
 * Three entry points map to the three ways a professional gets a document onto
 * their phone: pick a file (Files/Drive/iCloud), pick a photo of a page, or
 * scan a page with the camera. All three normalize to a `PickedFile` the API
 * client can upload; the backend's OCR path turns photos into text.
 */

import * as DocumentPicker from 'expo-document-picker';
import * as ImagePicker from 'expo-image-picker';

import type { PickedFile } from '@/api/types';

// Formats the backend can currently ingest (mirrors supported_extensions()).
const ACCEPTED_DOC_TYPES = [
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'application/msword',
  'application/rtf',
  'application/vnd.oasis.opendocument.text',
  'text/plain',
  'text/markdown',
  'text/csv',
];

// UUID pattern iOS uses as photo filenames — not human-readable.
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\./i;

function dateStamp(): string {
  const d = new Date();
  return d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })
    .replace(/ /g, ' '); // "12 Jul 2026"
}

/**
 * Return a clean, human-readable filename.
 *
 * - Document picker: always has a real name → preserve it (strip path prefix if present).
 * - Image picker: iOS often gives a UUID like "7A2F8B9C-….jpg" → replace with a
 *   friendly label. A real name like "IMG_1234.jpg" is kept as-is.
 * - Camera: never has a meaningful name → always generate "Scan, DD Mon YYYY.jpg".
 */
function cleanDocName(raw: string | null | undefined): string {
  if (!raw) return `Document ${dateStamp()}.pdf`;
  const base = decodeURIComponent(raw.split('/').pop() ?? raw);
  return base;
}

function cleanImageName(raw: string | null | undefined, ext = 'jpg'): string {
  if (!raw) return `Photo, ${dateStamp()}.${ext}`;
  const base = decodeURIComponent(raw.split('/').pop() ?? raw);
  // Replace UUID filenames with something readable.
  if (UUID_RE.test(base)) return `Photo, ${dateStamp()}.${ext}`;
  return base;
}

function scanName(ext = 'jpg'): string {
  return `Scan, ${dateStamp()}.${ext}`;
}

/** Open the system document picker (PDF/DOCX/TXT from Files, Drive, iCloud…). */
export async function pickDocument(): Promise<PickedFile | null> {
  const result = await DocumentPicker.getDocumentAsync({
    type: [...ACCEPTED_DOC_TYPES, 'image/*'],
    copyToCacheDirectory: true,
    multiple: false,
  });
  if (result.canceled || !result.assets?.length) return null;
  const asset = result.assets[0];
  const ext = (asset.mimeType ?? '').includes('image') ? 'jpg' : 'pdf';
  return {
    uri: asset.uri,
    name: cleanDocName(asset.name) || `Document ${dateStamp()}.${ext}`,
    mimeType: asset.mimeType ?? 'application/octet-stream',
    size: asset.size,
  };
}

/** Pick an existing photo of a document from the library. */
export async function pickImage(): Promise<PickedFile | null> {
  const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
  if (!perm.granted) throw new Error('Photo library permission was denied.');
  const result = await ImagePicker.launchImageLibraryAsync({
    mediaTypes: ['images'],
    quality: 0.9,
  });
  if (result.canceled || !result.assets?.length) return null;
  const asset = result.assets[0];
  const ext = (asset.mimeType ?? 'image/jpeg').split('/')[1] ?? 'jpg';
  return {
    uri: asset.uri,
    name: cleanImageName(asset.fileName, ext),
    mimeType: asset.mimeType ?? 'image/jpeg',
    size: asset.fileSize,
  };
}

/** Scan a paper document with the camera → OCR on the server. */
export async function scanWithCamera(): Promise<PickedFile | null> {
  const perm = await ImagePicker.requestCameraPermissionsAsync();
  if (!perm.granted) throw new Error('Camera permission was denied.');
  const result = await ImagePicker.launchCameraAsync({
    mediaTypes: ['images'],
    quality: 0.9,
  });
  if (result.canceled || !result.assets?.length) return null;
  const asset = result.assets[0];
  const ext = (asset.mimeType ?? 'image/jpeg').split('/')[1] ?? 'jpg';
  return {
    uri: asset.uri,
    name: scanName(ext),
    mimeType: asset.mimeType ?? 'image/jpeg',
    size: asset.fileSize,
  };
}
