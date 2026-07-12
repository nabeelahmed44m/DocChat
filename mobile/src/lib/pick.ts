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

function guessName(uri: string, fallbackExt: string): string {
  const tail = uri.split('/').pop();
  if (tail && tail.includes('.')) return decodeURIComponent(tail);
  return `scan-${Date.now()}.${fallbackExt}`;
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
  return {
    uri: asset.uri,
    name: asset.name ?? guessName(asset.uri, 'pdf'),
    mimeType: asset.mimeType ?? 'application/octet-stream',
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
  return {
    uri: asset.uri,
    name: asset.fileName ?? guessName(asset.uri, 'jpg'),
    mimeType: asset.mimeType ?? 'image/jpeg',
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
  return {
    uri: asset.uri,
    name: asset.fileName ?? guessName(asset.uri, 'jpg'),
    mimeType: asset.mimeType ?? 'image/jpeg',
  };
}
